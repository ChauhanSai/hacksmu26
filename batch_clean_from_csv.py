#!/usr/bin/env python3
"""
Batch-clean every WAV that appears in the hackathon rumble CSV.

Example:
  python batch_clean_from_csv.py \\
    --audio-dir "/path/to/Audio Files Master" \\
    --out-dir ./cleaned_batch

Uses the same CSV-driven windows as the web API (merge for masking, per-row labels).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import soundfile as sf

from elephant_audio_cleaner import SEGMENT_PAD, clean_audio, plot_spectrogram
from rumble_annotations import load_rumble_csv, merge_for_processing, pad_segments_for_display


def main() -> None:
    p = argparse.ArgumentParser(description="Batch clean WAVs using hackathon CSV timings.")
    p.add_argument(
        "--csv",
        type=Path,
        default=Path(__file__).resolve().parent / "data" / "rumbles_in_noise_for_hackathon.csv",
        help="Path to rumbles_in_noise_for_hackathon.csv",
    )
    p.add_argument("--audio-dir", type=Path, required=True, help="Folder containing the master WAV files")
    p.add_argument("--out-dir", type=Path, required=True, help="Output folder for cleaned WAVs + spectrograms")
    p.add_argument("--skip-spectrograms", action="store_true", help="Only write WAVs (faster)")
    args = p.parse_args()

    index = load_rumble_csv(args.csv)
    if not index:
        raise SystemExit(f"No rows loaded from {args.csv}")

    # Unique sound files that have at least one rumble-labeled row
    sound_files = sorted({fn for fn in index.keys()})
    args.out_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []
    ok = 0
    missing = 0
    failed = 0

    for fn in sound_files:
        wav_path = args.audio_dir / fn
        if not wav_path.is_file():
            print(f"[skip] missing file: {wav_path}")
            missing += 1
            continue
        rows = index[fn]
        try:
            duration_sec = float(sf.info(str(wav_path)).duration)
        except Exception as e:
            print(f"[fail] cannot read {wav_path}: {e}")
            failed += 1
            continue

        merged = merge_for_processing(rows, duration_sec, SEGMENT_PAD)
        display = pad_segments_for_display(rows, duration_sec, SEGMENT_PAD)
        if not merged:
            print(f"[skip] no valid windows after merge: {fn}")
            failed += 1
            continue

        stem = Path(fn).stem
        out_wav = args.out_dir / f"{stem}_elephant_only.wav"
        before_png = args.out_dir / f"{stem}_before.png"
        after_png = args.out_dir / f"{stem}_after.png"

        try:
            if not args.skip_spectrograms:
                plot_spectrogram(wav_path, before_png, "Before Cleaning")
            summary = clean_audio(
                wav_path,
                out_wav,
                segments_merged=merged,
                segments_display=display,
            )
            if not args.skip_spectrograms:
                plot_spectrogram(out_wav, after_png, "After Cleaning")
        except Exception as e:
            print(f"[fail] {fn}: {e}")
            failed += 1
            continue

        ok += 1
        manifest.append(
            {
                "source": str(wav_path),
                "cleaned_wav": str(out_wav),
                "annotations_source": summary.annotations_source,
                "n_segments": len(summary.segments),
                "labels": summary.segment_labels,
            }
        )
        print(f"[ok] {fn} -> {out_wav.name} ({len(summary.segments)} windows)")

    manifest_path = args.out_dir / "batch_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nDone: {ok} cleaned, {missing} missing inputs, {failed} failed. Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
