"""
Elephant Rumble Extraction Pipeline v2
=======================================
Spectrogram-informed approach based on visual analysis of provided spectrograms.

WHAT WE SEE IN THE SPECTROGRAMS:
- Noise (vehicles/airplanes/generators) = bright horizontal band spanning 100–700 Hz,
  constant across all time. This is stationary broadband noise.
- Elephant rumble = energy in the 0–180 Hz region that is DISTINCT from the noise floor.
  It appears as a darker, structured pattern in the bottom of the spectrogram.
- "Straight lines" = persistent horizontal bright bands at specific frequencies
  (e.g., ~175 Hz airplane tonal, ~100 Hz generator fundamental and harmonics).
  These are the exact lines the mentors said to target.

APPROACH:
1. Load full audio file
2. Identify noise-only segments (outside the CSV timestamp window)
3. Compute per-frequency noise power profile from those segments
4. For each STFT bin: if power >> noise floor → likely noise → subtract
5. Apply soft bandpass mask (8–180 Hz) to remove anything that escaped above
6. Reconstruct waveform via iSTFT
7. Trim to exact rumble timestamps

This mimics what you see in Audacity: look at the quiet sections of the spectrogram,
see the noise floor at each frequency, then subtract that floor from the rumble window.
"""

import os
import sys
import warnings
import numpy as np
import pandas as pd
import soundfile as sf
from scipy.signal import stft, istft, butter, filtfilt
warnings.filterwarnings("ignore")


# ─── PARAMETERS ───────────────────────────────────────────────────────────────
# Large FFT window for fine frequency resolution (≈5.4 Hz/bin at 44.1 kHz)
# This lets us target the specific Hz bands we see in the spectrograms
NFFT        = 8192
HOP         = 2048
WINDOW      = "hann"
RUMBLE_LO   = 8      # Hz — bottom of elephant rumble band
RUMBLE_HI   = 180    # Hz — top of elephant rumble band
# Spectral subtraction parameters
# α = over-subtraction: how aggressively to remove noise
# Higher α removes more noise but risks removing quiet rumble energy too
ALPHA       = 2.0
# β = spectral floor: minimum output level (prevents complete silence artifacts)
BETA        = 0.005
CONTEXT_SEC = 3.0    # seconds of audio before/after rumble to use as noise reference


def load_audio(path):
    """Load wav, convert to mono, return (waveform, sample_rate)."""
    wav, sr = sf.read(path)
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    return wav.astype(np.float64), sr


def get_noise_reference(waveform, sr, rumble_start, rumble_end):
    """
    Extract the noise-only portion of the recording.
    This is the key step: we use the same file but OUTSIDE the rumble window
    to estimate what the airplane/vehicle/generator sounds like alone.
    This is exactly what Audacity's noise reduction does — you select a
    'noise profile' region first, then apply it.
    """
    s0 = int(max(0, rumble_start - CONTEXT_SEC) * sr)
    s1 = int(rumble_start * sr)
    e0 = int(rumble_end * sr)
    e1 = int(min(len(waveform)/sr, rumble_end + CONTEXT_SEC) * sr)
    
    parts = []
    if s1 > s0:
        parts.append(waveform[s0:s1])
    if e1 > e0:
        parts.append(waveform[e0:e1])
    
    if parts:
        noise_ref = np.concatenate(parts)
    else:
        # Fallback: use entire file (less ideal but better than nothing)
        noise_ref = waveform
    
    return noise_ref


def compute_noise_profile(noise_ref, sr):
    """
    Compute per-frequency noise power spectrum from the noise reference.
    This produces the 'horizontal line' profile we see in the spectrogram —
    the average energy at each frequency when only noise is present.
    
    Returns: (frequencies_array, noise_power_array shaped (freq_bins, 1))
    """
    if len(noise_ref) < NFFT:
        # Pad if too short
        noise_ref = np.pad(noise_ref, (0, NFFT - len(noise_ref)))
    
    f, _, Zxx_noise = stft(
        noise_ref, fs=sr,
        nperseg=NFFT, noverlap=NFFT - HOP, window=WINDOW
    )
    
    # Per-bin average power across all noise frames
    noise_power = np.mean(np.abs(Zxx_noise) ** 2, axis=1, keepdims=True)
    return f, noise_power


def spectral_subtract(Zxx, noise_power, alpha=ALPHA, beta=BETA):
    """
    Core denoising operation.
    
    For each time-frequency bin:
      cleaned_power = max(signal_power - α * noise_power, β * signal_power)
    
    α > 1 means we subtract MORE than the estimated noise — this is
    'over-subtraction', which aggressively removes the noise but can
    create brief quiet gaps ('musical noise').
    β * signal_power is the floor — we never go below this, which 
    prevents complete silence in the output.
    
    The output magnitude is used with the ORIGINAL phase for reconstruction.
    This preserves the timing information (where the rumble starts/ends).
    """
    Sxx_mag   = np.abs(Zxx)
    Sxx_phase = np.angle(Zxx)
    
    Sxx_power = Sxx_mag ** 2
    cleaned   = np.maximum(
        Sxx_power - alpha * noise_power,
        beta * Sxx_power
    )
    cleaned_mag = np.sqrt(cleaned)
    
    # Reconstruct complex spectrogram: cleaned magnitude + original phase
    Zxx_clean = cleaned_mag * np.exp(1j * Sxx_phase)
    return Zxx_clean


def apply_elephant_band_mask(Zxx, f):
    """
    Apply a soft bandpass mask: keep only 8–180 Hz, taper the edges.
    
    This is the 'seeing the lines in the spectrogram' step:
    We know the elephant energy lives in a specific band. Everything
    above 180 Hz (the noise floor we see in the spectrograms as a
    bright horizontal expanse) gets zeroed out.
    
    The taper (instead of hard cutoff) prevents ringing artifacts.
    """
    mask = np.zeros(len(f))
    
    for i, freq in enumerate(f):
        if freq < RUMBLE_LO:
            # Below 8 Hz: taper up from 0
            if freq > 1:
                mask[i] = (freq - 1) / (RUMBLE_LO - 1)
        elif freq <= RUMBLE_HI:
            # Inside the elephant band: full pass
            mask[i] = 1.0
        elif freq <= RUMBLE_HI + 50:
            # 180–230 Hz: gentle roll-off (some harmonics live here)
            mask[i] = 1.0 - (freq - RUMBLE_HI) / 50.0
        else:
            # Above 230 Hz: zero — this is the noise floor we see in spectrograms
            mask[i] = 0.0
    
    return Zxx * mask[:, np.newaxis]


def detect_tonal_lines(noise_power, f, threshold_db=6):
    """
    Detect the 'straight horizontal lines' in the spectrogram —
    narrow-band tonal components from generators (60 Hz harmonics)
    and airplanes (propeller blade frequency).
    
    A tonal line appears as a frequency bin whose noise power is
    significantly above its neighbors. We identify these and apply
    extra suppression at those specific Hz.
    
    Returns list of (freq_hz, suppression_factor) tuples.
    """
    pwr_db = 10 * np.log10(noise_power[:, 0] + 1e-12)
    
    # Smooth the background (what the noise floor would be without tonals)
    from scipy.ndimage import uniform_filter1d
    smoothed = uniform_filter1d(pwr_db, size=15)
    
    # Find bins significantly above the smoothed floor
    excess_db = pwr_db - smoothed
    tonal_bins = np.where((excess_db > threshold_db) & (f > RUMBLE_LO) & (f < 800))[0]
    
    tonals = []
    for idx in tonal_bins:
        tonals.append((f[idx], excess_db[idx]))
    
    return tonals


def apply_tonal_notch(Zxx, f, tonals, notch_width_hz=3):
    """
    For each detected tonal line (straight horizontal line in spectrogram),
    apply a narrow notch filter at that exact frequency.
    This directly implements what the mentors described:
    'see the straight line → remove it'.
    """
    if not tonals:
        return Zxx
    
    Zxx_notched = Zxx.copy()
    freq_step   = f[1] - f[0] if len(f) > 1 else 1.0
    
    for freq_hz, excess_db in tonals:
        # How wide to notch: narrower for strong tones, barely touch weak ones
        width = notch_width_hz + min(excess_db / 10, 5)
        # Suppression strength proportional to how strong the tonal is
        suppression = max(0.05, 1.0 - min(excess_db / 30, 0.95))
        
        lo = np.searchsorted(f, freq_hz - width)
        hi = np.searchsorted(f, freq_hz + width) + 1
        Zxx_notched[lo:hi, :] *= suppression
    
    return Zxx_notched


def reconstruct_waveform(Zxx_clean, sr):
    """iSTFT back to time-domain waveform using same STFT parameters."""
    _, wav = istft(
        Zxx_clean, fs=sr,
        nperseg=NFFT, noverlap=NFFT - HOP, window=WINDOW
    )
    return wav


def bandpass_filter(waveform, sr, lo=RUMBLE_LO, hi=RUMBLE_HI):
    """
    Final safety bandpass: 8–180 Hz Butterworth.
    This is the last line of defense — removes any residual high-freq
    artifacts that survived the spectral subtraction.
    """
    nyq = sr / 2.0
    if hi >= nyq:
        hi = nyq * 0.95
    if lo <= 0:
        lo = 1.0
    
    # High-pass at lo Hz
    b, a = butter(4, lo / nyq, btype='high')
    wav  = filtfilt(b, a, waveform)
    # Low-pass at hi Hz
    b, a = butter(4, hi / nyq, btype='low')
    wav  = filtfilt(b, a, wav)
    return wav


def normalize(wav, target_peak=0.7):
    """Normalize output to target peak level."""
    peak = np.max(np.abs(wav))
    if peak > 1e-10:
        return wav * (target_peak / peak)
    return wav


def process_file(input_path, output_path, rumble_start, rumble_end, verbose=True):
    """
    Full pipeline for one rumble segment.
    
    Args:
        input_path:   Path to noisy WAV
        output_path:  Where to write cleaned WAV
        rumble_start: Start time in seconds (from CSV)
        rumble_end:   End time in seconds (from CSV)
    """
    if verbose:
        fname = os.path.basename(input_path)
        print(f"\n{'─'*60}")
        print(f"  File:   {fname}")
        print(f"  Rumble: {rumble_start:.3f}s → {rumble_end:.3f}s")
        print(f"{'─'*60}")
    
    # 1. Load
    waveform, sr = load_audio(input_path)
    if verbose:
        print(f"  Loaded: {len(waveform)/sr:.1f}s at {sr} Hz")
    
    # 2. Extract noise reference (sections of file OUTSIDE the rumble)
    noise_ref = get_noise_reference(waveform, sr, rumble_start, rumble_end)
    if verbose:
        print(f"  Noise reference: {len(noise_ref)/sr:.1f}s from non-rumble regions")
    
    # 3. Compute noise power profile (the 'horizontal line' pattern in spectrogram)
    f, noise_power = compute_noise_profile(noise_ref, sr)
    if verbose:
        peak_noise_hz = f[np.argmax(noise_power[:, 0])]
        print(f"  Peak noise frequency: {peak_noise_hz:.1f} Hz")
    
    # 4. Detect tonal lines (the specific bright horizontal lines the mentors mentioned)
    tonals = detect_tonal_lines(noise_power, f)
    if verbose and tonals:
        print(f"  Tonal lines detected: {[(f'{hz:.0f} Hz (+{db:.1f} dB)') for hz, db in tonals[:5]]}")
    
    # 5. STFT of the rumble segment (with context padding)
    ctx   = min(CONTEXT_SEC, rumble_start, (len(waveform)/sr) - rumble_end)
    t0    = int((rumble_start - ctx) * sr)
    t1    = int((rumble_end   + ctx) * sr)
    t0    = max(0, t0)
    t1    = min(len(waveform), t1)
    segment = waveform[t0:t1]
    
    f_seg, _, Zxx = stft(
        segment, fs=sr,
        nperseg=NFFT, noverlap=NFFT - HOP, window=WINDOW
    )
    if verbose:
        print(f"  STFT: {Zxx.shape[0]} freq bins × {Zxx.shape[1]} frames "
              f"({f_seg[1]-f_seg[0]:.2f} Hz/bin)")
    
    # 6. Spectral subtraction: remove the noise floor we estimated
    Zxx_clean = spectral_subtract(Zxx, noise_power)
    
    # 7. Notch the tonal lines (straight horizontal lines → zero them out)
    Zxx_clean = apply_tonal_notch(Zxx_clean, f_seg, tonals)
    
    # 8. Band mask: keep only the elephant frequency region (8–180 Hz)
    Zxx_clean = apply_elephant_band_mask(Zxx_clean, f_seg)
    if verbose:
        print(f"  Elephant band mask applied ({RUMBLE_LO}–{RUMBLE_HI} Hz)")
    
    # 9. Reconstruct waveform via iSTFT
    clean_wav = reconstruct_waveform(Zxx_clean, sr)
    if verbose:
        print(f"  iSTFT → {len(clean_wav)/sr:.2f}s waveform")
    
    # 10. Final bandpass filter (safety pass)
    clean_wav = bandpass_filter(clean_wav, sr)
    
    # 11. Trim to exact rumble window (remove context padding)
    trim_start = int(ctx * sr)
    rumble_dur = rumble_end - rumble_start
    trim_end   = trim_start + int(rumble_dur * sr)
    trim_end   = min(trim_end, len(clean_wav))
    clean_wav  = clean_wav[trim_start:trim_end]
    
    # 12. Normalize
    clean_wav = normalize(clean_wav)
    
    # 13. Save
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    sf.write(output_path, clean_wav, sr)
    
    if verbose:
        duration = len(clean_wav) / sr
        print(f"  ✓ Saved: {output_path}")
        print(f"    Duration: {duration:.2f}s | Sample rate: {sr} Hz")
    
    return clean_wav, sr


def batch_process(csv_path, audio_dir, output_dir):
    """Process all files in the CSV spreadsheet."""
    df = pd.read_csv(csv_path)
    os.makedirs(output_dir, exist_ok=True)
    
    results = []
    total   = len(df)
    success = 0
    
    print(f"\n{'='*60}")
    print(f"  BATCH MODE: {total} rumble annotations across {df['Sound_file'].nunique()} files")
    print(f"{'='*60}")
    
    for _, row in df.iterrows():
        fname  = row["Sound_file"]
        sel    = int(row["Selection"])
        start  = float(row["Start_time"])
        end    = float(row["End_time"])
        
        input_path = os.path.join(audio_dir, fname)
        if not os.path.exists(input_path):
            print(f"  ⚠ Not found: {fname} — skipping")
            results.append({"file": fname, "selection": sel, "status": "FILE_NOT_FOUND"})
            continue
        
        stem     = os.path.splitext(fname)[0]
        out_path = os.path.join(output_dir, f"{stem}_rumble_{sel:03d}_cleaned.wav")
        
        try:
            process_file(input_path, out_path, start, end, verbose=True)
            results.append({"file": fname, "selection": sel,
                            "start": start, "end": end,
                            "output": out_path, "status": "OK"})
            success += 1
        except Exception as e:
            print(f"  ✗ Error: {e}")
            results.append({"file": fname, "selection": sel,
                            "start": start, "end": end, "status": f"ERROR: {e}"})
    
    log_path = os.path.join(output_dir, "batch_log.csv")
    pd.DataFrame(results).to_csv(log_path, index=False)
    print(f"\n{'='*60}")
    print(f"  Done: {success}/{total} succeeded")
    print(f"  Log: {log_path}")
    print(f"{'='*60}")
    return results


# ─── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Elephant Rumble Extractor — spectrogram-informed noise removal"
    )
    parser.add_argument("--input",      help="Input WAV file path")
    parser.add_argument("--output",     help="Output WAV file path")
    parser.add_argument("--start",      type=float, help="Rumble start time (sec)")
    parser.add_argument("--end",        type=float, help="Rumble end time (sec)")
    parser.add_argument("--batch",      action="store_true", help="Batch all files from CSV")
    parser.add_argument("--csv",        default="audio_files.csv")
    parser.add_argument("--audio_dir",  default=".")
    parser.add_argument("--output_dir", default="cleaned_output")
    
    args = parser.parse_args()
    
    if args.batch:
        batch_process(args.csv, args.audio_dir, args.output_dir)
    elif args.input and args.output and args.start is not None and args.end is not None:
        process_file(args.input, args.output, args.start, args.end)
    else:
        parser.print_help()
        print("\nExample:")
        print("  python elephant_pipeline_v2.py \\")
        print("    --input  recordings/2000-24_generator_noise_2.wav \\")
        print("    --output cleaned/generator_2_rumble_086.wav \\")
        print("    --start  50.5826 \\")
        print("    --end    53.4560")
