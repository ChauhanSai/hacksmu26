# 🐘 Elephant Rumble Extraction Pipeline
### Northern Texas Hackathon — ElephantVoices Challenge

---

## What This Does

This pipeline takes a noisy WAV recording (with airplane, car, or generator noise)
and outputs a **clean audio file containing only the elephant rumble** — no other
sounds — trimmed precisely to the timestamps in the spreadsheet.

---

## Science Behind It

Based on three peer-reviewed papers:

| Paper | What it contributes |
|---|---|
| Keen et al. (2017), JASA | STFT parameters, elephant frequency range (8–180 Hz), noise characteristics |
| Bermant (2021), Scientific Reports | BioCPPNet U-Net denoising architecture, Wiener filter, SI-SDR metric |
| Geldenhuys & Niesler (2024), arXiv | AST transformer verification, frame-level detection |

---

## Pipeline Stages (in order)

```
NOISY WAV
  │
  ├─[1] STFT  (nfft=4096, hop=512, Hann window)
  │       → Complex spectrogram (magnitude + phase preserved)
  │
  ├─[2] Noise Power Estimation
  │       → Uses non-rumble frames as noise reference
  │
  ├─[3] Spectral Subtraction  (α=1.5, β=0.02)
  │       → Removes stationary noise: generator hum, steady engine
  │
  ├─[4] Wiener Filtering
  │       → Smooths noise removal, prevents "musical noise" artifacts
  │
  ├─[5] NMF Tonal Separation  (4 components)
  │       → Removes tonal engine harmonics (car RPM, generator cycles)
  │
  ├─[6] Soft Elephant Band Mask  (8–180 Hz, tapered edges)
  │       → Attenuates energy outside elephant frequency range
  │
  ├─[7] Phase-Consistent Reconstruction
  │       → Retains original phase → iSTFT → waveform
  │
  ├─[8] Bandpass Filter  (8–180 Hz, 4th order Butterworth)
  │       → Final cleanup of any residual high-freq artifacts
  │
  └─[9] Trim + Normalize
          → Exact rumble segment, normalized to -3 dBFS
          → OUTPUT: clean elephant-only WAV
```

---

## Installation

```bash
python3 -m pip install -r requirements.txt
```

## Web Frontend

The local UI is now audio-only.
The web flow uses:
1. A noisy `.wav` upload

It returns:
1. A cleaned elephant-only WAV
2. An automatically generated before spectrogram
3. An automatically generated after spectrogram
4. Detected rumble-window timestamps used by the cleaner

Run a local upload UI around the pipeline:

```bash
python3 app.py
```

Then open [http://127.0.0.1:5000](http://127.0.0.1:5000).

What the UI supports:
1. Upload a `.wav` file
2. Auto-generate a before spectrogram from the uploaded audio
3. Detect likely elephant-rumble windows from the recording itself
4. Preview the cleaned output in the browser
5. Compare before and after spectrograms
6. Download the cleaned WAV

---

## Usage

### Single File
```bash
python elephant_pipeline.py \
  --input  04-040920-02_vehicle_1.wav \
  --output cleaned/vehicle_1_rumble_001.wav \
  --start  30.6492 \
  --end    33.4161
```

### Batch Mode (all 38 files from CSV)
```bash
python elephant_pipeline.py \
  --batch \
  --csv       audio_files.csv \
  --audio_dir /path/to/wav/files \
  --output_dir cleaned_output
```

This will:
1. Process all 212 rumble annotations from the spreadsheet
2. Output one WAV per rumble annotation
3. Save a `processing_log.csv` summarizing results

---

## Output Files

| File | Description |
|---|---|
| `{stem}_rumble_{NNN}.wav` | Cleaned elephant-only audio, exact rumble duration |
| `processing_log.csv` | Status log for each annotation |

---

## Quality Targets

| Metric | Target | What it means |
|---|---|---|
| **SI-SDR** | > 20 dB | Signal quality vs. noise (26.1 dB achieved by BioCPPNet) |
| **Band energy** | > 90% in 8–180 Hz | Confirms only elephant frequencies remain |
| **F0 deviation** | < 5% | Fundamental frequency preserved |

---

## Key Design Decisions

**Why NFFT=4096?**  
At 44.1 kHz, NFFT=4096 gives ~10.7 Hz per bin — fine enough to resolve the 18–34 Hz
elephant F0 range. The original Keen (2017) paper used NFFT=1024 (43 Hz/bin) which
is too coarse for infrasound.

**Why preserve phase?**  
BioCPPNet (Bermant 2021) showed that magnitude-only processing degrades waveform
reconstruction. This pipeline keeps the complex STFT throughout and applies the
gain function to the original complex coefficients.

**Why not just apply a 180 Hz low-pass filter first?**  
Because vehicle, airplane, and generator noise all have strong low-frequency energy
that overlaps the elephant band (8–180 Hz). A naïve low-pass filter would keep
most of the noise. Intelligent separation (spectral subtraction + Wiener + NMF)
must happen first.
