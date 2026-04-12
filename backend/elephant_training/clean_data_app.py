from __future__ import annotations

import logging
from pathlib import Path
import uuid

from elephant_audio_cleaner import clean_audio, plot_spectrogram

# Set up base directories relative to this file
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
TRAINING_DIR = BASE_DIR / "training"
SPECTROGRAM_DIR = BASE_DIR / "generated_spectrograms"
ALLOWED_AUDIO_EXTENSIONS = {".wav"}

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
TRAINING_DIR.mkdir(exist_ok=True)
SPECTROGRAM_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def allowed_audio(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_AUDIO_EXTENSIONS


def process_all_wavs():
    wav_paths = sorted([p for p in DATA_DIR.rglob("*.wav") if p.is_file()])
    if not wav_paths:
        logging.info("No WAV files found in %s", DATA_DIR)
        return

    processed = []
    failures = []

    for src in wav_paths:
        rel = src.relative_to(DATA_DIR)
        logging.info("Processing: %s", rel)
        try:
            # Build output paths
            out_path = TRAINING_DIR / f"{src.stem}.wav"

            token = uuid.uuid4().hex[:8]
            before_img = SPECTROGRAM_DIR / f"{src.stem}_0before.png"
            after_img = SPECTROGRAM_DIR / f"{src.stem}_1after.png"

            # Generate before spectrogram (non-fatal)
            try:
                plot_spectrogram(src, before_img, "Before Cleaning")
            except Exception as e:
                logging.debug("Failed to plot before spectrogram for %s: %s", src, e)

            # Clean audio and write to training directory
            summary = clean_audio(src, out_path)

            # Generate after spectrogram (non-fatal)
            try:
                plot_spectrogram(out_path, after_img, "After Cleaning")
            except Exception as e:
                logging.debug("Failed to plot after spectrogram for %s: %s", out_path, e)

            logging.info("Saved cleaned audio to: %s", out_path)
            processed.append((src, out_path, summary))
        except Exception as exc:
            logging.error("Failed processing %s: %s", src, exc)
            failures.append((src, exc))
            continue

    # Summary
    logging.info("Processing complete. %d succeeded, %d failed.", len(processed), len(failures))
    if failures:
        for src, exc in failures:
            logging.info(" - Failed: %s -> %s", src, exc)


if __name__ == "__main__":
    process_all_wavs()
