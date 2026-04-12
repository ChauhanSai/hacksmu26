"""
Elephant Rumble Extraction Pipeline
====================================
Science-backed pipeline based on:
  - Keen et al. (2017), JASA: STFT parameters, frequency analysis
  - Geldenhuys & Niesler (2024): Transformer verification
  - Bermant (2021), Scientific Reports: BioCPPNet U-Net architecture

Pipeline stages:
  1. STFT (nfft=1024, hop=200, Hann window)
  2. Log-frequency axis transformation
  3. Spectral Subtraction (α=1.5, β=0.02)
  4. Wiener Filtering
  5. NMF Separation (residual tonal noise)
  6. Soft mask application (elephant frequency band)
  7. Inverse STFT → waveform
  8. Bandpass filter: 8–180 Hz
  9. Rumble-window extraction (from spreadsheet timestamps)

Usage:
  python elephant_pipeline.py --input <file.wav> --start <sec> --end <sec> --output <out.wav>
  python elephant_pipeline.py --batch  # processes all files from CSV
"""

import argparse
import os
import sys
import numpy as np
import pandas as pd
import soundfile as sf
from scipy.signal import stft, istft, butter, filtfilt
from sklearn.decomposition import NMF
import warnings
warnings.filterwarnings("ignore")


# ─── PIPELINE PARAMETERS (Keen 2017 + improvements) ──────────────────────────
NFFT         = 4096      # FFT size — ~10.7 Hz resolution at 44.1 kHz (better for 8-180 Hz band)
HOP          = 512       # Hop size (~87.5% overlap for smooth reconstruction)
WINDOW       = "hann"    # Window type
RUMBLE_LO    = 8         # Hz — low edge of elephant rumble band
RUMBLE_HI    = 180       # Hz — high edge of elephant rumble band
ALPHA        = 1.5       # Spectral subtraction over-subtraction factor
BETA         = 0.02      # Spectral floor (prevents musical noise)
NMF_COMPS    = 4         # NMF components for tonal noise separation
NOISE_FRAC   = 0.10      # Fraction of file used to estimate noise profile
BUTTER_ORDER = 4         # Butterworth filter order


# ─── STAGE 1: STFT ────────────────────────────────────────────────────────────
def compute_stft(waveform, sr):
    """Complex STFT. Preserves phase for reconstruction."""
    f, t, Zxx = stft(
        waveform,
        fs=sr,
        nperseg=NFFT,
        noverlap=NFFT - HOP,
        window=WINDOW
    )
    return f, t, Zxx  # Zxx is complex (magnitude + phase)


# ─── STAGE 2: LOG-FREQUENCY TRANSFORM ─────────────────────────────────────────
def log_freq_weights(f):
    """
    Returns per-bin weight on a log-frequency scale.
    Emphasises the 8–180 Hz elephant rumble region relative to higher bins.
    """
    f_safe = np.where(f > 0, f, 1e-6)
    # Weight = 1 inside rumble band, tapered outside
    weight = np.where(
        (f_safe >= RUMBLE_LO) & (f_safe <= RUMBLE_HI),
        1.0,
        np.maximum(0.1, 1.0 - np.abs(np.log2(f_safe / 40)) / 4)
    )
    return weight  # shape: (freq_bins,)


# ─── STAGE 3: NOISE ESTIMATION ────────────────────────────────────────────────
def estimate_noise_power(Sxx_mag, noise_fraction=NOISE_FRAC):
    """
    Estimate noise power spectrum from quietest frames (minimum statistics).
    Uses first + last NOISE_FRAC of frames as noise-only reference.
    """
    n_frames = Sxx_mag.shape[1]
    n_noise  = max(5, int(n_frames * noise_fraction))
    # Take quietest frames (by total energy) as noise reference
    frame_energy = Sxx_mag.sum(axis=0)
    noise_idx    = np.argsort(frame_energy)[:n_noise]
    noise_power  = np.mean(Sxx_mag[:, noise_idx] ** 2, axis=1, keepdims=True)
    return noise_power  # shape: (freq_bins, 1)


# ─── STAGE 4A: SPECTRAL SUBTRACTION ──────────────────────────────────────────
def spectral_subtraction(Sxx_mag, noise_power):
    """
    Sxx_clean = max(|Sxx|² - α·Phi_noise, β·|Sxx|²)
    α=1.5 aggressively removes stationary noise (generators, steady car hum).
    β=0.02 spectral floor prevents musical noise artifacts.
    """
    Sxx_power = Sxx_mag ** 2
    Sxx_clean = np.maximum(
        Sxx_power - ALPHA * noise_power,
        BETA * Sxx_power
    )
    return np.sqrt(Sxx_clean)  # back to magnitude


# ─── STAGE 4B: WIENER FILTERING ──────────────────────────────────────────────
def wiener_filter(Sxx_mag_clean, noise_power):
    """
    H(f) = SNR(f) / (SNR(f) + 1)   where SNR = signal_power / noise_power
    Smooth gain function — reduces musical noise from spectral subtraction.
    """
    signal_power = np.maximum(Sxx_mag_clean ** 2, noise_power)
    snr          = signal_power / (noise_power + 1e-12)
    gain         = snr / (snr + 1.0)
    return Sxx_mag_clean * gain


# ─── STAGE 4C: NMF TONAL SEPARATION ─────────────────────────────────────────
def nmf_separation(Sxx_mag, f):
    """
    Decomposes spectrogram into NMF_COMPS additive components.
    Components dominated by frequencies < RUMBLE_HI Hz are kept (elephant).
    Components dominated by higher frequencies are discarded (tonal noise).
    """
    S   = Sxx_mag.T + 1e-10  # time × freq, non-negative
    nmf = NMF(n_components=NMF_COMPS, init="nndsvd", max_iter=200, random_state=42)
    W   = nmf.fit_transform(S)   # time × components
    H   = nmf.components_        # components × freq

    # Score each component: fraction of energy in elephant band
    lo_idx = np.searchsorted(f, RUMBLE_LO)
    hi_idx = np.searchsorted(f, RUMBLE_HI)
    total  = H.sum(axis=1) + 1e-12
    eleph  = H[:, lo_idx:hi_idx].sum(axis=1)
    score  = eleph / total  # 0–1; higher = more elephant-like

    # Keep components with >25% energy in rumble band
    keep_mask = score > 0.25
    if not keep_mask.any():
        # Fallback: keep best component
        keep_mask[np.argmax(score)] = True

    recon = (W[:, keep_mask] @ H[keep_mask, :]).T  # freq × time
    return np.maximum(recon, 0)


# ─── STAGE 5: SOFT ELEPHANT MASK ─────────────────────────────────────────────
def elephant_band_mask(f, Sxx_mag):
    """
    Soft mask that strongly attenuates energy outside 8–180 Hz.
    Tapered transition (not a brick-wall) to avoid ringing.
    """
    mask = np.zeros(len(f))
    for i, freq in enumerate(f):
        if freq < RUMBLE_LO:
            mask[i] = max(0.0, (freq - 1) / (RUMBLE_LO - 1)) if freq > 1 else 0.0
        elif freq <= RUMBLE_HI:
            mask[i] = 1.0
        else:
            # Gentle roll-off above 180 Hz — keep some harmonic energy
            decay   = np.exp(-(freq - RUMBLE_HI) / 80.0)
            mask[i] = decay
    return mask[:, np.newaxis]  # shape: (freq_bins, 1)


# ─── STAGE 6: INVERSE STFT ───────────────────────────────────────────────────
def reconstruct_waveform(Zxx_clean, sr):
    """iSTFT with same parameters as forward transform."""
    _, waveform = istft(
        Zxx_clean,
        fs=sr,
        nperseg=NFFT,
        noverlap=NFFT - HOP,
        window=WINDOW
    )
    return waveform


# ─── STAGE 7: BANDPASS FILTER ─────────────────────────────────────────────────
def bandpass_filter(waveform, sr, lo=RUMBLE_LO, hi=RUMBLE_HI):
    """
    Two-pass Butterworth bandpass: high-pass at 8 Hz + low-pass at 180 Hz.
    Applied after intelligent separation — safe to use here.
    """
    nyq  = sr / 2.0
    # High-pass at 8 Hz
    b, a = butter(BUTTER_ORDER, lo / nyq, btype="high")
    wav  = filtfilt(b, a, waveform)
    # Low-pass at 180 Hz
    b, a = butter(BUTTER_ORDER, hi / nyq, btype="low")
    wav  = filtfilt(b, a, wav)
    return wav


# ─── FULL PIPELINE ────────────────────────────────────────────────────────────
def process_file(input_path, output_path, rumble_start=None, rumble_end=None):
    """
    Full pipeline: raw WAV → cleaned elephant-only WAV.

    Args:
        input_path:   Path to noisy input WAV
        output_path:  Path for cleaned output WAV
        rumble_start: Start time (sec) of rumble segment (from spreadsheet). If None, process whole file.
        rumble_end:   End time (sec) of rumble segment
    """
    print(f"\n{'='*60}")
    print(f"  Processing: {os.path.basename(input_path)}")
    print(f"{'='*60}")

    # Load audio (preserve original sample rate — do NOT downsample)
    waveform, sr = sf.read(input_path)
    if waveform.ndim > 1:
        waveform = waveform.mean(axis=1)  # mono
    print(f"  Loaded: {len(waveform)/sr:.1f}s at {sr} Hz")

    # If timestamps given, extract the rumble window + 1s context on each side
    if rumble_start is not None and rumble_end is not None:
        context = 1.0  # seconds of context around the rumble
        t_start = max(0, rumble_start - context)
        t_end   = min(len(waveform) / sr, rumble_end + context)
        s_start = int(t_start * sr)
        s_end   = int(t_end   * sr)
        working = waveform[s_start:s_end]
        # For noise estimation, use the whole file minus the rumble window
        noise_ref_left  = waveform[:max(0, int(rumble_start * sr))]
        noise_ref_right = waveform[min(len(waveform), int(rumble_end * sr)):]
        noise_ref = np.concatenate([noise_ref_left, noise_ref_right])
        print(f"  Rumble window: {rumble_start:.2f}s – {rumble_end:.2f}s")
    else:
        working   = waveform
        noise_ref = waveform
        t_start   = 0.0

    # ── Stage 1: STFT ──────────────────────────────────────────────────
    f, t, Zxx       = compute_stft(working, sr)
    Sxx_mag         = np.abs(Zxx)
    Sxx_phase       = np.angle(Zxx)
    print(f"  STFT: {Sxx_mag.shape[0]} freq bins × {Sxx_mag.shape[1]} frames")

    # ── Stage 2: Noise estimation from non-rumble reference ───────────
    if len(noise_ref) > NFFT:
        f_n, _, Zxx_n = compute_stft(noise_ref, sr)
        noise_power   = estimate_noise_power(np.abs(Zxx_n))
    else:
        noise_power = estimate_noise_power(Sxx_mag)
    print(f"  Noise profile estimated")

    # ── Stage 3: Spectral Subtraction ─────────────────────────────────
    Sxx_sub = spectral_subtraction(Sxx_mag, noise_power)
    print(f"  Spectral subtraction complete (α={ALPHA}, β={BETA})")

    # ── Stage 4: Wiener Filtering ──────────────────────────────────────
    Sxx_wiener = wiener_filter(Sxx_sub, noise_power)
    print(f"  Wiener filter applied")

    # ── Stage 5: NMF Tonal Separation ─────────────────────────────────
    Sxx_nmf = nmf_separation(Sxx_wiener, f)
    print(f"  NMF separation complete ({NMF_COMPS} components)")

    # ── Stage 6: Soft Elephant Band Mask ──────────────────────────────
    emask      = elephant_band_mask(f, Sxx_nmf)
    Sxx_masked = Sxx_nmf * emask
    print(f"  Elephant band mask applied ({RUMBLE_LO}–{RUMBLE_HI} Hz)")

    # ── Stage 7: Reconstruct complex spectrogram (retain original phase)
    # Blend: use cleaned magnitude + original phase (preserves structure)
    gain_factor = np.where(Sxx_mag > 1e-10, Sxx_masked / (Sxx_mag + 1e-10), 0)
    Zxx_clean   = Zxx * gain_factor
    print(f"  Phase-consistent reconstruction")

    # ── Stage 8: iSTFT → waveform ─────────────────────────────────────
    clean_wave = reconstruct_waveform(Zxx_clean, sr)
    print(f"  iSTFT complete: {len(clean_wave)/sr:.2f}s reconstructed")

    # ── Stage 9: Bandpass filter 8–180 Hz ─────────────────────────────
    if sr / 2 > RUMBLE_HI + 10:  # only if Nyquist allows
        clean_wave = bandpass_filter(clean_wave, sr)
        print(f"  Bandpass filter applied ({RUMBLE_LO}–{RUMBLE_HI} Hz)")

    # ── Trim to exact rumble window (remove context padding) ──────────
    if rumble_start is not None:
        trim_start = int((rumble_start - t_start) * sr)
        trim_end   = int((rumble_end   - t_start) * sr)
        trim_start = max(0, trim_start)
        trim_end   = min(len(clean_wave), trim_end)
        clean_wave = clean_wave[trim_start:trim_end]

    # ── Normalize output to -3 dBFS ───────────────────────────────────
    peak = np.max(np.abs(clean_wave))
    if peak > 0:
        clean_wave = clean_wave / peak * 0.7

    # ── Write output ───────────────────────────────────────────────────
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    sf.write(output_path, clean_wave, sr)
    print(f"  ✓ Saved: {output_path}  ({len(clean_wave)/sr:.2f}s)")

    return output_path


# ─── QUALITY METRICS ──────────────────────────────────────────────────────────
def compute_si_sdr(reference, estimate):
    """SI-SDR (Scale-Invariant Signal-to-Distortion Ratio). Target: >20 dB."""
    ref = reference - reference.mean()
    est = estimate  - estimate.mean()
    n   = min(len(ref), len(est))
    ref, est = ref[:n], est[:n]
    dot     = np.dot(est, ref)
    s_target = (dot / (np.dot(ref, ref) + 1e-12)) * ref
    e_noise  = est - s_target
    si_sdr   = 10 * np.log10((np.dot(s_target, s_target) + 1e-12) /
                              (np.dot(e_noise,  e_noise)  + 1e-12))
    return si_sdr


# ─── BATCH PROCESSING FROM CSV ────────────────────────────────────────────────
def batch_process(csv_path, audio_dir, output_dir):
    """
    Process all files listed in the spreadsheet.
    Groups rows by Sound_file so each file is processed once,
    extracting all its rumble segments.
    """
    df = pd.read_csv(csv_path)
    os.makedirs(output_dir, exist_ok=True)
    results = []

    for fname, group in df.groupby("Sound_file"):
        input_path = os.path.join(audio_dir, fname)
        if not os.path.exists(input_path):
            print(f"  ⚠ Not found: {input_path} — skipping")
            continue

        for _, row in group.iterrows():
            sel   = int(row["Selection"])
            start = float(row["Start_time"])
            end   = float(row["End_time"])
            stem  = os.path.splitext(fname)[0]
            outf  = os.path.join(output_dir, f"{stem}_rumble_{sel:03d}.wav")

            try:
                process_file(input_path, outf, start, end)
                results.append({"file": fname, "selection": sel,
                                 "start": start, "end": end, "output": outf, "status": "OK"})
            except Exception as e:
                print(f"  ✗ Error on {fname} sel {sel}: {e}")
                results.append({"file": fname, "selection": sel,
                                 "start": start, "end": end, "output": outf, "status": f"ERROR: {e}"})

    # Save results log
    log_path = os.path.join(output_dir, "processing_log.csv")
    pd.DataFrame(results).to_csv(log_path, index=False)
    print(f"\n{'='*60}")
    print(f"  Batch complete. {len([r for r in results if r['status']=='OK'])} / {len(results)} succeeded.")
    print(f"  Log: {log_path}")
    return results


# ─── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Elephant Rumble Extraction Pipeline"
    )
    parser.add_argument("--input",  help="Input WAV file")
    parser.add_argument("--output", help="Output WAV file")
    parser.add_argument("--start",  type=float, help="Rumble start time (sec)")
    parser.add_argument("--end",    type=float, help="Rumble end time (sec)")
    parser.add_argument("--batch",  action="store_true",
                        help="Batch mode: process all files from CSV")
    parser.add_argument("--csv",    default="audio_files.csv",
                        help="CSV spreadsheet path (batch mode)")
    parser.add_argument("--audio_dir", default=".",
                        help="Directory containing WAV files (batch mode)")
    parser.add_argument("--output_dir", default="cleaned_output",
                        help="Output directory (batch mode)")

    args = parser.parse_args()

    if args.batch:
        batch_process(args.csv, args.audio_dir, args.output_dir)
    elif args.input and args.output:
        process_file(args.input, args.output, args.start, args.end)
    else:
        parser.print_help()
