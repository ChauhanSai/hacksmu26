"""
Elephant Rumble Cleaner — Full Three-Input Pipeline
=====================================================
Uses ALL THREE inputs together, exactly as the mentors described:

  INPUT 1: Spectrogram image (.png)
    → Read pixel brightness per frequency row
    → Identify the DARK zone (elephant rumble region)  
    → Identify the BRIGHT zone (noise region)
    → Find bright horizontal tonal lines (the "straight lines" = generator/airplane tonals)

  INPUT 2: CSV spreadsheet (start/end timestamps)
    → Know WHEN in the audio the rumble occurs
    → Use non-rumble sections as noise reference (same idea as Audacity "Get Noise Profile")

  INPUT 3: Audio file (.wav)
    → The signal to clean
    → Output: cleaned WAV containing only the elephant rumble

HOW IT WORKS (mirrors what you see in Audacity):
  1. Read the spectrogram image → find which Hz bands are noise vs elephant
  2. Get noise fingerprint from the audio sections OUTSIDE the rumble timestamp  
  3. Subtract that noise fingerprint from the rumble section, bin by bin
  4. Notch out the specific tonal lines identified from the spectrogram image
  5. Zero everything above the frequency where the image shows noise starts
  6. Reconstruct audio via iSTFT and trim to exact timestamps

Usage:
  python elephant_cleaner.py \\
    --audio     recordings/2000-24_generator_noise_2.wav \\
    --image     spectrograms/2000-24_generator_noise_2_Selection_86.png \\
    --csv       audio_files.csv \\
    --selection 86 \\
    --output    cleaned/gen2_rumble_086.wav
"""

import os
import sys
import argparse
import warnings
import numpy as np
import pandas as pd
import soundfile as sf
from PIL import Image
from scipy.signal import stft, istft, butter, filtfilt
from scipy.ndimage import uniform_filter1d
warnings.filterwarnings("ignore")


# ─── CONSTANTS ────────────────────────────────────────────────────────────────
SPECTROGRAM_FREQ_MAX = 700   # Hz — Y axis max in all provided spectrograms (0.7 kHz)
NFFT        = 8192           # FFT window — gives ~5.4 Hz/bin at 44.1 kHz
HOP         = 2048
WINDOW      = "hann"
ALPHA       = 2.5            # Spectral subtraction aggressiveness
BETA        = 0.002          # Spectral floor (prevents silence artifacts)
CONTEXT_SEC = 4.0            # Seconds before/after rumble used as noise reference


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1 — READ THE SPECTROGRAM IMAGE
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_spectrogram_image(image_path, verbose=True):
    """
    Read the spectrogram PNG and extract:
      - Which Hz bands are DARK (quiet = elephant region → PRESERVE)
      - Which Hz bands are BRIGHT (loud = noise → REMOVE)
      - Where the specific tonal horizontal lines are (→ NOTCH)

    The spectrogram Y-axis runs from 0 Hz (bottom) to 700 Hz (top).
    Bright pixels = high energy = noise.
    Dark pixels   = low energy  = quiet (elephant rumble lives here).
    """
    if verbose:
        print(f"\n  [IMAGE] Reading: {os.path.basename(image_path)}")

    img = Image.open(image_path).convert("L")
    arr = np.array(img, dtype=np.float32)
    H, W = arr.shape

    # ── Find plot boundaries (exclude title, axis labels, white margins) ──
    col_dark = np.array([(arr[:, c] < 230).sum() for c in range(W)])
    row_dark  = np.array([(arr[r, :] < 230).sum() for r in range(H)])

    col_active = np.where(col_dark > 30)[0]
    row_active = np.where(row_dark  > 30)[0]

    if len(col_active) == 0 or len(row_active) == 0:
        if verbose:
            print(f"  [IMAGE] Warning: could not find plot area, using defaults")
        return {"elephant_lo": 8, "elephant_hi": 180,
                "noise_lo": 180, "noise_hi": 700, "tonal_hz": []}

    plot_left   = col_active[0]
    plot_right  = col_active[-1]
    plot_top    = row_active[0]
    plot_bottom = row_active[-1]
    plot        = arr[plot_top:plot_bottom, plot_left:plot_right]
    n_rows      = plot.shape[0]

    if verbose:
        print(f"  [IMAGE] Plot area: {plot.shape[1]}w × {n_rows}h px")

    # ── Per-Hz-band mean brightness ──
    # Row 0 of plot = top = SPECTROGRAM_FREQ_MAX Hz
    # Row n_rows-1  = bottom = 0 Hz
    band_size_hz  = 10  # resolution: check every 10 Hz
    band_brightness = {}
    for hz_lo in range(0, SPECTROGRAM_FREQ_MAX, band_size_hz):
        hz_hi  = hz_lo + band_size_hz
        row_lo = int(n_rows * (1.0 - hz_hi / SPECTROGRAM_FREQ_MAX))
        row_hi = int(n_rows * (1.0 - hz_lo / SPECTROGRAM_FREQ_MAX))
        row_lo = max(0, min(row_lo, n_rows - 1))
        row_hi = max(row_lo + 1, min(row_hi, n_rows))
        band_brightness[hz_lo] = float(plot[row_lo:row_hi, :].mean())

    hz_vals = np.array(sorted(band_brightness.keys()))
    br_vals = np.array([band_brightness[h] for h in hz_vals])

    # ── Separate axis margins from real content ──
    # The very bottom rows (0–100 Hz in image) are often white margins.
    # Real signal starts where brightness drops from the white margin plateau.
    # Ignore hz < 50 (usually axis margin, not real signal).
    valid_mask = hz_vals >= 50
    valid_hz   = hz_vals[valid_mask]
    valid_br   = br_vals[valid_mask]

    # ── Identify dark zone (elephant) and bright zone (noise) ──
    # Dark = below mean − 0.5*std. Bright = above mean.
    mean_br  = valid_br.mean()
    std_br   = valid_br.std()
    dark_thr = mean_br - 0.5 * std_br

    dark_bands  = valid_hz[valid_br < dark_thr]
    bright_bands = valid_hz[valid_br >= mean_br]

    if len(dark_bands) > 0:
        elephant_lo = max(8,   int(dark_bands.min()))
        elephant_hi = min(700, int(dark_bands.max()) + band_size_hz)
    else:
        # Fallback: assume standard elephant range
        elephant_lo, elephant_hi = 8, 180

    if len(bright_bands) > 0:
        noise_lo = int(bright_bands.min())
        noise_hi = int(bright_bands.max()) + band_size_hz
    else:
        noise_lo, noise_hi = elephant_hi, 700

    # ── Detect tonal lines (the specific bright horizontal lines) ──
    # A tonal = a narrow Hz band significantly brighter than its neighbors
    smoothed_br = uniform_filter1d(valid_br, size=5)
    tonal_excess = valid_br - smoothed_br
    tonal_thr    = tonal_excess.std() * 1.8

    tonal_hz = []
    for i, hz in enumerate(valid_hz):
        if tonal_excess[i] > tonal_thr and elephant_lo < hz < 600:
            # Only care about tonals that are in or near the elephant band
            # (high-freq tonals above 600 Hz don't matter — we remove all of those anyway)
            tonal_hz.append(hz)

    # Group nearby tonal detections
    if tonal_hz:
        grouped = []
        g = [tonal_hz[0]]
        for i in range(1, len(tonal_hz)):
            if tonal_hz[i] - tonal_hz[i-1] <= 30:
                g.append(tonal_hz[i])
            else:
                grouped.append(int(np.mean(g)))
                g = [tonal_hz[i]]
        grouped.append(int(np.mean(g)))
        tonal_hz = grouped

    if verbose:
        print(f"  [IMAGE] Elephant band (DARK region):  {elephant_lo}–{elephant_hi} Hz → PRESERVE")
        print(f"  [IMAGE] Noise band (BRIGHT region):   {noise_lo}–{noise_hi} Hz → REMOVE")
        if tonal_hz:
            print(f"  [IMAGE] Tonal lines detected: {tonal_hz} Hz → NOTCH")
        else:
            print(f"  [IMAGE] No narrow tonal lines detected (broadband noise only)")

    return {
        "elephant_lo": elephant_lo,
        "elephant_hi": elephant_hi,
        "noise_lo":    noise_lo,
        "noise_hi":    noise_hi,
        "tonal_hz":    tonal_hz,
        "brightness_profile": dict(zip(hz_vals.tolist(), br_vals.tolist()))
    }


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2 — READ TIMESTAMPS FROM CSV
# ═══════════════════════════════════════════════════════════════════════════════

def get_timestamps(csv_path, selection_id=None, sound_file=None, verbose=True):
    """
    Read start/end timestamps from the CSV spreadsheet.
    Can look up by Selection number or Sound_file name.
    Returns list of (start_sec, end_sec) tuples.
    """
    df = pd.read_csv(csv_path)

    if selection_id is not None:
        rows = df[df["Selection"] == int(selection_id)]
    elif sound_file is not None:
        fname = os.path.basename(sound_file)
        rows = df[df["Sound_file"] == fname]
    else:
        raise ValueError("Provide either --selection or --sound_file to look up timestamps")

    if len(rows) == 0:
        raise ValueError(f"No entries found in CSV for selection={selection_id}, file={sound_file}")

    timestamps = [(float(r.Start_time), float(r.End_time)) for _, r in rows.iterrows()]

    if verbose:
        print(f"\n  [CSV]   Found {len(timestamps)} rumble annotation(s):")
        for i, (s, e) in enumerate(timestamps):
            print(f"          [{i+1}] {s:.3f}s → {e:.3f}s  (duration: {e-s:.2f}s)")

    return timestamps


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3 — LOAD AUDIO
# ═══════════════════════════════════════════════════════════════════════════════

def load_audio(audio_path, verbose=True):
    wav, sr = sf.read(audio_path)
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    wav = wav.astype(np.float64)
    if verbose:
        print(f"\n  [AUDIO] Loaded: {os.path.basename(audio_path)}")
        print(f"          Duration: {len(wav)/sr:.1f}s  |  Sample rate: {sr} Hz")
    return wav, sr


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4 — ESTIMATE NOISE FINGERPRINT (from non-rumble audio sections)
# ═══════════════════════════════════════════════════════════════════════════════

def get_noise_fingerprint(wav, sr, rumble_start, rumble_end, verbose=True):
    """
    Extract audio sections OUTSIDE the rumble window → these are noise-only.
    This is identical to what Audacity does when you select a 'noise profile' region.
    Combined with the spectrogram image, we now have TWO ways of knowing what the
    noise looks like:
      - Visually: the bright horizontal band in the image
      - Acoustically: the actual sound before/after the rumble
    """
    pre_start  = max(0, rumble_start - CONTEXT_SEC)
    pre_end    = rumble_start
    post_start = rumble_end
    post_end   = min(len(wav)/sr, rumble_end + CONTEXT_SEC)

    parts = []
    if pre_end > pre_start:
        parts.append(wav[int(pre_start * sr):int(pre_end * sr)])
    if post_end > post_start:
        parts.append(wav[int(post_start * sr):int(post_end * sr)])

    noise_ref = np.concatenate(parts) if parts else wav

    if verbose:
        print(f"\n  [NOISE] Reference: {len(noise_ref)/sr:.1f}s of audio outside rumble window")

    if len(noise_ref) < NFFT:
        noise_ref = np.pad(noise_ref, (0, NFFT - len(noise_ref)))

    f, _, Zxx_n = stft(noise_ref, fs=sr, nperseg=NFFT, noverlap=NFFT-HOP, window=WINDOW)
    noise_power = np.mean(np.abs(Zxx_n) ** 2, axis=1, keepdims=True)  # shape: (bins, 1)

    return f, noise_power


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 5 — CLEAN: SPECTRAL SUBTRACTION + TONAL NOTCH + BAND MASK
# ═══════════════════════════════════════════════════════════════════════════════

def clean_segment(wav, sr, rumble_start, rumble_end,
                  noise_power, f,
                  image_info, verbose=True):
    """
    The actual cleaning step — uses all three information sources:
    
    From IMAGE:    elephant_lo/hi, noise_lo/hi, tonal_hz
    From CSV:      rumble_start, rumble_end  
    From AUDIO:    noise_power (estimated from non-rumble sections)
    """
    elephant_lo = image_info["elephant_lo"]
    elephant_hi = image_info["elephant_hi"]
    tonal_hz    = image_info["tonal_hz"]

    # Extract segment with context
    ctx   = min(CONTEXT_SEC, rumble_start, len(wav)/sr - rumble_end)
    s0    = max(0, int((rumble_start - ctx) * sr))
    s1    = min(len(wav), int((rumble_end   + ctx) * sr))
    seg   = wav[s0:s1]

    # STFT of segment
    f_seg, _, Zxx = stft(seg, fs=sr, nperseg=NFFT, noverlap=NFFT-HOP, window=WINDOW)

    if verbose:
        hz_per_bin = f_seg[1] - f_seg[0] if len(f_seg) > 1 else 1
        print(f"\n  [CLEAN] Segment: {len(seg)/sr:.2f}s  |  "
              f"STFT: {Zxx.shape[0]} bins × {Zxx.shape[1]} frames  |  "
              f"{hz_per_bin:.2f} Hz/bin")

    # ── 1. Spectral subtraction (remove the noise floor) ──
    Sxx_mag   = np.abs(Zxx)
    Sxx_phase = np.angle(Zxx)
    Sxx_pwr   = Sxx_mag ** 2
    cleaned   = np.maximum(Sxx_pwr - ALPHA * noise_power, BETA * Sxx_pwr)
    cleaned_mag = np.sqrt(cleaned)

    if verbose:
        print(f"  [CLEAN] Spectral subtraction: α={ALPHA}, β={BETA}")

    # ── 2. Notch the specific tonal lines from the image ──
    if tonal_hz:
        for hz in tonal_hz:
            # Find the bin closest to this frequency
            bin_idx    = np.argmin(np.abs(f_seg - hz))
            notch_bins = 3  # how many bins either side to zero
            lo = max(0, bin_idx - notch_bins)
            hi = min(cleaned_mag.shape[0], bin_idx + notch_bins + 1)
            cleaned_mag[lo:hi, :] *= 0.02  # suppress to 2%
        if verbose:
            print(f"  [CLEAN] Notch filters applied at: {tonal_hz} Hz")

    # ── 3. Band mask: image told us where the elephant lives ──
    #       Keep: elephant_lo to elephant_hi (the dark region in the image)
    #       Remove: everything above elephant_hi (the bright noise region)
    mask = np.zeros(len(f_seg))
    for i, freq in enumerate(f_seg):
        if freq < elephant_lo:
            # Taper up to low edge
            if freq > max(1, elephant_lo - 10):
                mask[i] = (freq - (elephant_lo - 10)) / 10.0
        elif freq <= elephant_hi:
            # Full pass — this is the elephant band the image identified
            mask[i] = 1.0
        elif freq <= elephant_hi + 30:
            # Gentle roll-off at the boundary
            mask[i] = 1.0 - (freq - elephant_hi) / 30.0
        else:
            # Zero — this is the noise region the image showed as bright
            mask[i] = 0.0

    cleaned_mag = cleaned_mag * mask[:, np.newaxis]

    if verbose:
        print(f"  [CLEAN] Band mask: KEEP {elephant_lo}–{elephant_hi} Hz, "
              f"REMOVE >{elephant_hi} Hz")

    # ── 4. Reconstruct complex spectrogram (cleaned magnitude + original phase) ──
    ratio    = np.where(Sxx_mag > 1e-12, cleaned_mag / (Sxx_mag + 1e-12), 0.0)
    Zxx_out  = Zxx * ratio

    # ── 5. iSTFT → time domain ──
    _, out_wav = istft(Zxx_out, fs=sr, nperseg=NFFT, noverlap=NFFT-HOP, window=WINDOW)

    # ── 6. Safety bandpass filter ──
    nyq = sr / 2.0
    if elephant_hi < nyq - 10 and elephant_lo > 0:
        b, a = butter(4, elephant_lo / nyq, btype='high')
        out_wav = filtfilt(b, a, out_wav)
        b, a = butter(4, min(elephant_hi, nyq * 0.95) / nyq, btype='low')
        out_wav = filtfilt(b, a, out_wav)
        if verbose:
            print(f"  [CLEAN] Butterworth bandpass: {elephant_lo}–{elephant_hi} Hz")

    # ── 7. Trim to exact rumble window ──
    trim_s = int(ctx * sr)
    trim_e = trim_s + int((rumble_end - rumble_start) * sr)
    trim_e = min(trim_e, len(out_wav))
    out_wav = out_wav[trim_s:trim_e]

    # ── 8. Normalize ──
    peak = np.max(np.abs(out_wav))
    if peak > 1e-10:
        out_wav = out_wav / peak * 0.7

    return out_wav


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE — ties all three inputs together
# ═══════════════════════════════════════════════════════════════════════════════

def run_pipeline(audio_path, image_path, csv_path,
                 selection_id=None, output_path=None, verbose=True):
    """
    Full pipeline using all three inputs.
    """
    print(f"\n{'═'*62}")
    print(f"  ELEPHANT RUMBLE CLEANER")
    print(f"  Audio:       {os.path.basename(audio_path)}")
    print(f"  Spectrogram: {os.path.basename(image_path)}")
    print(f"  CSV:         {os.path.basename(csv_path)}")
    print(f"{'═'*62}")

    # ── INPUT 1: Spectrogram image ──────────────────────────────────────────
    image_info = analyze_spectrogram_image(image_path, verbose=verbose)

    # ── INPUT 2: CSV timestamps ─────────────────────────────────────────────
    timestamps = get_timestamps(
        csv_path,
        selection_id=selection_id,
        sound_file=audio_path,
        verbose=verbose
    )

    # ── INPUT 3: Audio ──────────────────────────────────────────────────────
    wav, sr = load_audio(audio_path, verbose=verbose)

    # ── Process each rumble annotation ──────────────────────────────────────
    all_cleaned = []
    for i, (rumble_start, rumble_end) in enumerate(timestamps):
        print(f"\n  {'─'*58}")
        print(f"  Rumble {i+1}/{len(timestamps)}: {rumble_start:.3f}s → {rumble_end:.3f}s")

        # Noise fingerprint from audio (informed by image timestamps)
        f, noise_power = get_noise_fingerprint(
            wav, sr, rumble_start, rumble_end, verbose=verbose
        )

        # Clean
        cleaned = clean_segment(
            wav, sr, rumble_start, rumble_end,
            noise_power, f, image_info, verbose=verbose
        )
        all_cleaned.append(cleaned)

    # ── Save output ─────────────────────────────────────────────────────────
    if len(all_cleaned) == 1:
        final = all_cleaned[0]
    else:
        # Multiple rumbles: concatenate with 0.1s silence gap
        gap = np.zeros(int(0.1 * sr))
        final = np.concatenate([c for pair in zip(all_cleaned, [gap]*len(all_cleaned))
                                 for c in pair][:-1])

    if output_path is None:
        stem       = os.path.splitext(os.path.basename(audio_path))[0]
        sel_tag    = f"_sel{selection_id}" if selection_id else ""
        output_path = f"{stem}{sel_tag}_elephant_only.wav"

    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
    sf.write(output_path, final, sr)

    print(f"\n  {'═'*58}")
    print(f"  ✓ DONE")
    print(f"  Output:   {output_path}")
    print(f"  Duration: {len(final)/sr:.2f}s  |  Sample rate: {sr} Hz")
    print(f"  {'═'*58}\n")

    return output_path, final, sr


# ═══════════════════════════════════════════════════════════════════════════════
# BATCH MODE — process every file in the CSV
# ═══════════════════════════════════════════════════════════════════════════════

def run_batch(csv_path, audio_dir, image_dir, output_dir, verbose=False):
    """
    Process all files listed in the CSV.
    Automatically finds the matching spectrogram image for each selection.
    """
    df = pd.read_csv(csv_path)
    os.makedirs(output_dir, exist_ok=True)
    results = []

    print(f"\n{'═'*62}")
    print(f"  BATCH MODE: {len(df)} annotations across {df['Sound_file'].nunique()} files")
    print(f"{'═'*62}")

    for _, row in df.iterrows():
        fname  = row["Sound_file"]
        sel    = int(row["Selection"])
        start  = float(row["Start_time"])
        end    = float(row["End_time"])

        audio_path = os.path.join(audio_dir, fname)
        if not os.path.exists(audio_path):
            print(f"  ⚠ Audio not found: {fname}")
            results.append({"file": fname, "sel": sel, "status": "AUDIO_NOT_FOUND"})
            continue

        # Look for matching spectrogram image
        stem = os.path.splitext(fname)[0]
        image_candidates = [
            os.path.join(image_dir, f"{stem}_Selection_{sel}.png"),
            os.path.join(image_dir, f"{stem}_sel_{sel}.png"),
        ]
        # Also search for any image matching the stem
        image_path = None
        for cand in image_candidates:
            if os.path.exists(cand):
                image_path = cand
                break
        if image_path is None:
            # Fallback: find any image with this stem
            for f_name in os.listdir(image_dir):
                if stem in f_name and f_name.endswith(".png"):
                    image_path = os.path.join(image_dir, f_name)
                    break

        if image_path is None:
            print(f"  ⚠ No spectrogram image found for {fname} sel {sel} — skipping")
            results.append({"file": fname, "sel": sel, "status": "IMAGE_NOT_FOUND"})
            continue

        out_path = os.path.join(output_dir, f"{stem}_sel{sel:03d}_cleaned.wav")
        try:
            run_pipeline(
                audio_path=audio_path,
                image_path=image_path,
                csv_path=csv_path,
                selection_id=sel,
                output_path=out_path,
                verbose=verbose
            )
            results.append({"file": fname, "sel": sel, "output": out_path, "status": "OK"})
        except Exception as e:
            print(f"  ✗ Error on {fname} sel {sel}: {e}")
            results.append({"file": fname, "sel": sel, "status": f"ERROR: {e}"})

    log_path = os.path.join(output_dir, "batch_log.csv")
    pd.DataFrame(results).to_csv(log_path, index=False)
    ok = sum(1 for r in results if r["status"] == "OK")
    print(f"\n  Batch complete: {ok}/{len(results)} succeeded. Log: {log_path}")


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Elephant Rumble Cleaner — uses spectrogram image + CSV + audio",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:

  Single file (specifying Selection number from CSV):
    python elephant_cleaner.py \\
      --audio     recordings/2000-24_generator_noise_2.wav \\
      --image     spectrograms/2000-24_generator_noise_2_Selection_86.png \\
      --csv       audio_files.csv \\
      --selection 86 \\
      --output    cleaned/gen2_sel086.wav

  Single file (auto-finds timestamps by filename):
    python elephant_cleaner.py \\
      --audio     recordings/1989-08_airplane_01.wav \\
      --image     spectrograms/1989-08_airplane_01_Selection_28.png \\
      --csv       audio_files.csv \\
      --output    cleaned/airplane_1989_cleaned.wav

  Batch mode (all files in CSV):
    python elephant_cleaner.py \\
      --batch \\
      --csv        audio_files.csv \\
      --audio_dir  recordings/ \\
      --image_dir  spectrograms/ \\
      --output_dir cleaned/
        """
    )

    parser.add_argument("--audio",      help="Input WAV file")
    parser.add_argument("--image",      help="Spectrogram PNG for this file")
    parser.add_argument("--csv",        required=True, help="Spreadsheet with timestamps")
    parser.add_argument("--selection",  type=int, help="Selection number from CSV")
    parser.add_argument("--output",     help="Output WAV path")
    parser.add_argument("--batch",      action="store_true")
    parser.add_argument("--audio_dir",  default="recordings/")
    parser.add_argument("--image_dir",  default="spectrograms/")
    parser.add_argument("--output_dir", default="cleaned/")
    parser.add_argument("--quiet",      action="store_true", help="Reduce output verbosity")

    args = parser.parse_args()

    if args.batch:
        run_batch(args.csv, args.audio_dir, args.image_dir,
                  args.output_dir, verbose=not args.quiet)
    elif args.audio and args.image:
        run_pipeline(
            audio_path=args.audio,
            image_path=args.image,
            csv_path=args.csv,
            selection_id=args.selection,
            output_path=args.output,
            verbose=not args.quiet
        )
    else:
        parser.print_help()
