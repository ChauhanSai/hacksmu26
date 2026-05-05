# Elephant Training Data Pipeline

This directory contains the pipeline for processing raw elephant audio recordings into cleaned, segmented data ready for training models.

## Setup Instructions

### 1. Install Dependencies
Ensure you have the required Python libraries installed:
```bash
pip install librosa soundfile numpy scipy matplotlib
```

### 2. Prepare Data
Place your raw `.wav` recordings into the `data/` directory:
- Path: `backend/elephant_training/data/`
- The scripts will recursively find all `.wav` files within this folder.

### 3. Python Path
Since `clean_data_app.py` imports utilities from the project root, you may need to add the root directory to your `PYTHONPATH`:
```bash
export PYTHONPATH=$PYTHONPATH:$(pwd)/../..
```

---

## Processing Workflow

### Step 1: Clean the Audio
Run the cleaning script to remove background noise and isolate elephant rumbles/vocalizations.

```bash
python clean_data_app.py
```

**Output of `clean_data_app.py`:**
- **Cleaned WAVs**: Processed audio files are saved to the `training/` directory. These files have noise suppressed and are normalized for consistency.
- **Spectrograms**: For every processed file, two images are generated in `generated_spectrograms/`:
    - `[filename]_0before.png`: Spectrogram of the raw audio.
    - `[filename]_1after.png`: Spectrogram of the cleaned audio, showing isolated frequencies.
- **Console Logs**: Summary of successful and failed processing attempts.

### Step 2: Segment the Audio
Once you have cleaned audio in the `training/` folder, run the segmentation script to split them into individual clips.

```bash
python segment.py
```

**Output of `segment.py`:**
- **Audio Segments**: Individual `.wav` clips of detected activity are saved to the `segmented/` directory (e.g., `my_audio_seg001.wav`). 
    - Each segment is at least 1 second long.
    - Includes a 0.5-second buffer at the start and end for context.
- **segments.csv**: A metadata file that maps each segment to its parent source file.

---

## Directory Summary
- `data/`: Raw input files.
- `training/`: Output of `clean_data_app.py` (Cleaned full-length files).
- `generated_spectrograms/`: Visualizations of the cleaning process.
- `segmented/`: Output of `segment.py` (Individual training clips).
- `segments.csv`: Mapping of segments to original files.
