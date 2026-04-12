# Pachyderm Intelligence Terminal

A computational bioacoustics platform for analyzing elephant vocalizations. This system extracts acoustic features from elephant calls, clusters them into distinct call types, and maps them to behavioral contexts.

## Project Structure

```
hacksmu26/
├── frontend/                    # Web dashboard
│   ├── index.html              # Landing page
│   ├── analysis.html           # Analysis dashboard
│   ├── cleanup.html            # Audio cleanup terminal
│   ├── css/styles.css          # Dark institutional theme
│   └── js/                     # Frontend scripts
├── backend/
│   ├── elephant_linguistics/   # Call analysis pipeline
│   └── elephant_ethogram/      # Ethogram data processing
├── app.py                      # Flask API for audio cleanup
├── elephant_audio_cleaner.py   # Audio cleaning module
└── requirements.txt            # Python dependencies
```

## Quick Start

### 1. Install Dependencies

```bash
cd hacksmu26

# Install root dependencies (for audio cleanup)
pip install -r requirements.txt

# Install linguistics pipeline dependencies
pip install -r backend/elephant_linguistics/requirements.txt
```

### 2. Run the Linguistics Analysis Pipeline

```bash
cd backend/elephant_linguistics

# Generate sample data (optional, for testing)
python generate_sample_data.py

# Run the full analysis pipeline
python run_from_csv.py --csv sample_data/features.csv
```

This will:
- Analyze elephant calls and cluster them into call types
- Train context classifiers
- Generate visualizations and export data to the frontend

### 3. Start the Frontend Dashboard

```bash
cd frontend

# Start a local HTTP server
python -m http.server 8080
```

Then open http://localhost:8080 in your browser.

### 4. Start the Audio Cleanup Backend (Optional)

```bash
cd hacksmu26

# Start the Flask API server
python app.py
```

The audio cleanup API will run at http://127.0.0.1:5000

Then navigate to http://localhost:8080/cleanup.html to use the audio cleanup feature.

## Features

### Analysis Dashboard
- **Call-type clustering** — UMAP visualization of acoustic clusters
- **PMI heatmap** — Symbol × context association matrix
- **Transition matrix** — Call sequence patterns
- **Vowel space** — F1/F2 formant analysis
- **Caller identification** — Individual voice fingerprints
- **Interpretation cards** — Per-call behavioral predictions

### Audio Cleanup Terminal
- Upload noisy WAV recordings
- Automatic rumble detection (8–180 Hz)
- Spectral subtraction noise removal
- Tonal line notch filtering
- Before/after spectrogram comparison
- Download cleaned audio

## Tech Stack

- **Frontend**: HTML, Tailwind CSS, Plotly.js
- **Backend**: Python, Flask, scikit-learn, librosa
- **Audio Processing**: scipy, soundfile, matplotlib

## Requirements

- Python 3.10+
- Modern web browser

## License

HackSMU 2026 Project
