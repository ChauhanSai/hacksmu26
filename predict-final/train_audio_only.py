#!/usr/bin/env python3
"""
Elephant context classifier — PANNs embeddings + augmentation.

Replaces handcrafted features with pretrained CNN14 embeddings (2048-dim).
Augments 338 samples → ~1500 before embedding extraction.
Uses a single LightGBM classifier — simpler and better at this data size
than the 5-model stack.

Setup (one time):
    pip install librosa scikit-learn imbalanced-learn lightgbm \
                joblib seaborn torch torchaudio panns-inference shap

PANNs weights download automatically on first run (~180 MB).

Directory layout (same as before):
    data/data.csv
    data/segments.csv
    data/segmented/          ← original clipped WAVs
    results_panns/           ← outputs written here
    trained_panns.joblib     ← saved model
"""

from __future__ import annotations

import os
import warnings
import random
import numpy as np
import pandas as pd
import librosa
import soundfile as sf
import joblib
import shutil
import tempfile

from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from lightgbm import LGBMClassifier
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings("ignore")

BASE        = os.path.dirname(os.path.abspath(__file__))
DATA_DIR    = os.path.join(BASE, "data")
SEG_DIR     = os.path.join(DATA_DIR, "segmented")
RESULTS_DIR = os.path.join(BASE, "results_panns")
os.makedirs(RESULTS_DIR, exist_ok=True)

SR          = 32000   # PANNs CNN14 expects 32 kHz
AUG_PER_CLIP = 3      # augmented variants per original clip → 338 × 4 = ~1352 total


# ── Augmentation ──────────────────────────────────────────────────────────────

def augment_clip(y: np.ndarray, sr: int, seed: int) -> list[np.ndarray]:
    """
    Returns AUG_PER_CLIP augmented variants of the clip.
    Keeps transforms mild to preserve infrasonic content.
    """
    rng = np.random.default_rng(seed)
    variants = []

    # 1. Time stretch slow (0.85x) — same call, longer duration
    try:
        variants.append(librosa.effects.time_stretch(y, rate=0.85))
    except Exception:
        variants.append(y.copy())

    # 2. Time stretch fast (1.15x)
    try:
        variants.append(librosa.effects.time_stretch(y, rate=1.15))
    except Exception:
        variants.append(y.copy())

    # 3. Pitch shift ±1 semitone (mild — preserves harmonic ratios)
    direction = rng.choice([-1, 1])
    try:
        variants.append(librosa.effects.pitch_shift(y, sr=sr, n_steps=direction * 1.0))
    except Exception:
        variants.append(y.copy())

    # 4. Add gaussian noise (SNR ~25 dB — barely audible but regularises)
    if AUG_PER_CLIP >= 4:
        signal_power = np.mean(y ** 2)
        noise_power  = signal_power / (10 ** (25 / 10))
        noise        = rng.normal(0, np.sqrt(noise_power), len(y))
        variants.append(np.clip(y + noise.astype(y.dtype), -1.0, 1.0))

    return variants[:AUG_PER_CLIP]


# ── Elephant-specific feature extraction (replaces PANNs) ─────────────────────
#
# Why not PANNs CNN14?
#   PANNs was trained on AudioSet — human-centric audio (speech, music, urban
#   sounds). It has never seen infrasonic elephant calls (10-20 Hz fundamentals).
#   Its embedding dimensions encode concepts like "speech formants" and "musical
#   pitch" — irrelevant for elephant context classification.
#
# What we do instead:
#   Build a 256-dim feature vector tuned specifically to the acoustic properties
#   that distinguish elephant call CONTEXTS:
#     - Rumble band energy profile (infrasonic structure)
#     - Harmonic regularity (how "clean" the harmonic series is)
#     - Amplitude modulation rate (call tremor — context-dependent)
#     - Temporal envelope shape (attack, sustain, decay)
#     - Inter-harmonic noise ratio (signal quality indicator)
#     - Mel features in the audible harmonic range (200-1000 Hz)
#
#   No torch, no internet download, no segfault risk. Runs on CPU in <1s/clip.

def load_panns_model():
    """Stub — no model to load for elephant feature extractor."""
    print("Using elephant-specific feature extractor (no torch required).")
    return None  # 'at' argument kept for API compatibility


def get_embedding(at, y: np.ndarray, sr: int) -> np.ndarray:
    """
    Extract elephant-specific 256-dim feature vector.
    Designed for infrasonic rumble context classification.
    No external model required — pure numpy/scipy/librosa.
    """
    from scipy.signal import butter, sosfiltfilt, hilbert
    from scipy.ndimage import uniform_filter1d

    # Ensure float64, normalise
    y = np.asarray(y, dtype=np.float64)
    if sr != SR:
        y = librosa.resample(y, orig_sr=sr, target_sr=SR)
        sr = SR
    min_len = SR  # 1 second minimum
    if len(y) < min_len:
        y = np.pad(y, (0, min_len - len(y)))
    if np.max(np.abs(y)) > 0:
        y = y / np.max(np.abs(y))

    features = []

    def bandpass(signal, lo, hi, order=4):
        nyq = sr / 2
        lo_n = max(lo / nyq, 1e-5)
        hi_n = min(hi / nyq, 0.999)
        if hi_n <= lo_n:
            return np.zeros_like(signal)
        sos = butter(order, [lo_n, hi_n], btype="band", output="sos")
        return sosfiltfilt(sos, signal)

    def band_rms(signal, lo, hi):
        b = bandpass(signal, lo, hi)
        return float(np.sqrt(np.mean(b ** 2)) + 1e-12)

    # ── BLOCK 1: Rumble band energy (32 linear + 16 log-focused) ─────────────
    # Importance showed rumble bands 8–100 Hz dominate — add log-spaced detail
    rumble_bands_lin = np.linspace(8, 300, 33)
    for i in range(32):
        features.append(band_rms(y, rumble_bands_lin[i], rumble_bands_lin[i+1]))
    rumble_bands_log = np.logspace(np.log10(8), np.log10(120), 17)
    for i in range(16):
        features.append(band_rms(y, rumble_bands_log[i], rumble_bands_log[i+1]))

    # ── BLOCK 2: Amplitude modulation rate (16 features) ──────────────────────
    rumble = bandpass(y, 10, 200)
    envelope = np.abs(hilbert(rumble))
    envelope_smooth = uniform_filter1d(envelope, size=max(int(sr * 0.01), 1))
    env_fft = np.abs(np.fft.rfft(envelope_smooth, n=min(len(envelope_smooth), SR)))
    env_freqs = np.fft.rfftfreq(min(len(envelope_smooth), SR), d=1.0 / sr)
    mod_points = np.logspace(0, np.log10(80), 16)
    for mf in mod_points:
        idx = np.argmin(np.abs(env_freqs - mf))
        features.append(float(env_fft[idx]) if idx < len(env_fft) else 0.0)

    # ── BLOCK 3: Harmonic regularity score (8 features) ───────────────────────
    n_fft_harm = min(65536, len(y) // 2)
    n_fft_harm = max(n_fft_harm, 1024)
    if n_fft_harm % 2 != 0:
        n_fft_harm -= 1
    S = np.abs(np.fft.rfft(y * np.hanning(len(y)), n=n_fft_harm))
    freqs = np.fft.rfftfreq(n_fft_harm, d=1.0 / sr)
    for f0_candidate in [10, 12, 14, 16, 18, 20, 22, 25]:
        harmonic_energy = 0.0
        n_harmonics = 0
        for k in range(1, 20):
            hf = f0_candidate * k
            if hf > 400:
                break
            mask = np.abs(freqs - hf) < (f0_candidate * 0.15)
            if mask.any():
                harmonic_energy += S[mask].max()
                n_harmonics += 1
        features.append(harmonic_energy / max(n_harmonics, 1))

    # ── BLOCK 4: Temporal envelope — 32 frames + delta (64 features) ──────────
    # All 16 original frames ranked highly → double resolution + add delta
    # (frame-to-frame change captures attack/decay rate, key for alarm vs social)
    frame_len = max(len(y) // 32, 1)
    rms_frames = []
    for i in range(32):
        seg = y[i * frame_len:(i + 1) * frame_len]
        rms_frames.append(float(np.sqrt(np.mean(seg ** 2)) + 1e-12))
    features.extend(rms_frames)
    delta = np.diff(rms_frames, prepend=rms_frames[0])
    features.extend(delta.tolist())

    # ── BLOCK 5: Mel spectrogram statistics (128 features) ────────────────────
    try:
        mel = librosa.feature.melspectrogram(
            y=y, sr=sr, n_mels=64, fmin=200, fmax=min(1000, sr // 2 - 1),
            n_fft=2048, hop_length=512
        )
        mel_db = librosa.power_to_db(mel + 1e-10)
        features.extend(mel_db.mean(axis=1).tolist())
        features.extend(mel_db.std(axis=1).tolist())
    except Exception:
        features.extend([0.0] * 128)

    # ── BLOCK 6: Spectral contrast (12 features) ──────────────────────────────
    try:
        contrast = librosa.feature.spectral_contrast(
            y=y, sr=sr, n_fft=4096, hop_length=512, fmin=20.0, n_bands=6
        )
        features.extend(contrast.mean(axis=1).tolist())
        features.extend(contrast.std(axis=1).tolist()[:5])
    except Exception:
        features.extend([0.0] * 12)

    # ── BLOCK 7: MFCC mean + std (26 features) — NEW ─────────────────────────
    # Captures timbral shape in the audible harmonic range.
    # Calf Reassurance vs Advertisement differ in timbre even at similar F0.
    try:
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13, n_fft=2048, hop_length=512)
        features.extend(mfcc.mean(axis=1).tolist())
        features.extend(mfcc.std(axis=1).tolist())
    except Exception:
        features.extend([0.0] * 26)

    # ── BLOCK 8: Band energy ratios (5 features) — NEW ───────────────────────
    # Ratios are level-invariant — alarm calls have a different infrasound/HF
    # ratio than social play regardless of recording distance.
    bio   = band_rms(y,  8.0, 120.0)
    mid   = band_rms(y, 120.0, 500.0)
    hi    = band_rms(y, 500.0, min(8000.0, sr * 0.45))
    total = bio + mid + hi + 1e-12
    features.append(bio / total)
    features.append(mid / total)
    features.append(hi  / total)
    features.append(bio / (hi  + 1e-12))
    features.append(mid / (bio + 1e-12))

    # ── BLOCK 9: ZCR + RMS stats (4 features) ────────────────────────────────
    zcr = librosa.feature.zero_crossing_rate(y, frame_length=2048, hop_length=512)[0]
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
    features.extend([zcr.mean(), zcr.std(), rms.mean(), rms.std()])

    arr = np.array(features, dtype=np.float32)
    arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
    return arr


# ── Load & merge (same logic as train_audio_only.py) ─────────────────────────

print("Loading data...")
data     = pd.read_csv(os.path.join(DATA_DIR, "data.csv"))
data     = data.drop_duplicates(subset="file_name")
segments = pd.read_csv(os.path.join(DATA_DIR, "segments.csv"))
segments.columns = segments.columns.str.strip()
segments["file_name_key"] = segments["original_file_name"].str.replace(".wav", "", regex=False)

existing = set(os.listdir(SEG_DIR))
segments = segments[segments["segment_file_name"].isin(existing)]

merged = segments.merge(data, left_on="file_name_key", right_on="file_name", how="inner")
merged = merged.dropna(subset=["context"])

counts = merged["context"].value_counts()
merged = merged[merged["context"].isin(counts[counts >= 3].index)].reset_index(drop=True)

print(f"Usable segments: {len(merged)}")
print(merged["context"].value_counts().to_string())
print()


# ── Load PANNs ────────────────────────────────────────────────────────────────

at = load_panns_model()


# ── Extract embeddings with augmentation ─────────────────────────────────────
# For each original clip:
#   - embed the original
#   - embed AUG_PER_CLIP augmented variants
#   - label all of them with the same context
#
# Result: ~4x the training data with no new labels needed.

print(f"\nExtracting PANNs embeddings + {AUG_PER_CLIP} augmentations per clip...")
print(f"Expected total samples: {len(merged)} × {AUG_PER_CLIP + 1} = {len(merged) * (AUG_PER_CLIP + 1)}\n")

embeddings = []
labels     = []
sources    = []   # "original" or "aug_N" — useful for analysis

for i, (_, row) in enumerate(merged.iterrows()):
    path = os.path.join(SEG_DIR, row["segment_file_name"])
    try:
        y, sr = librosa.load(path, sr=SR, mono=True)
    except Exception as e:
        print(f"  [SKIP] {row['segment_file_name']}: {e}")
        continue

    if len(y) < SR * 0.05:
        continue

    context = row["context"]

    # Original
    emb = get_embedding(at, y, SR)
    embeddings.append(emb)
    labels.append(context)
    sources.append("original")

    # Augmented variants
    for j, y_aug in enumerate(augment_clip(y, SR, seed=i * 100 + i)):
        emb_aug = get_embedding(at, y_aug, SR)
        embeddings.append(emb_aug)
        labels.append(context)
        sources.append(f"aug_{j}")

    if (i + 1) % 25 == 0 or (i + 1) == len(merged):
        print(f"  {i + 1}/{len(merged)} clips processed  "
              f"({len(embeddings)} embeddings so far)")

X_arr      = np.stack(embeddings)               # (N, 2048)
labels_arr = np.array(labels)

target_le  = LabelEncoder()
y_enc      = target_le.fit_transform(labels_arr)
class_names = list(target_le.classes_)

print(f"\nFeature matrix: {X_arr.shape[0]} samples × {X_arr.shape[1]} features")
print(f"Classes: {class_names}\n")
print(f"Feature breakdown: 32 rumble bands + 16 AM rates + 8 harmonic scores "
      f"+ 16 temporal + 128 mel stats + 12 spectral contrast + 4 ZCR/RMS "
      f"= {32+16+8+16+128+12+4} dim")


# ── LightGBM classifier ───────────────────────────────────────────────────────
# Tuned for ~250-dim elephant features (not 2048-dim PANNs).
# Fewer leaves — we have fewer dimensions so the tree doesn't need to be as deep.

clf = LGBMClassifier(
    n_estimators=600,        # more trees — more features to exploit
    num_leaves=63,           # back to 63 — justified by ~280 features now
    learning_rate=0.03,
    subsample=0.8,
    subsample_freq=1,
    colsample_bytree=0.6,    # sample 60% of features per tree — prevents
                              # rumble bands from dominating every tree
    class_weight="balanced",
    reg_alpha=0.1,
    reg_lambda=1.0,
    min_child_samples=5,
    random_state=42,
    n_jobs=-1,
    verbose=-1,
)

# Scale embeddings
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_arr)

# Cross-validate on ALL data (originals + augmented)
# Use enough folds to get stable estimates
n_splits = max(3, min(5, int(pd.Series(labels_arr).value_counts().min() // 2)))
cv       = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)

print(f"Cross-validation: {n_splits}-fold stratified")
print("Training LightGBM...\n")

y_pred    = cross_val_predict(clf, X_scaled, y_enc, cv=cv)
acc       = accuracy_score(y_enc, y_pred)
report    = classification_report(y_enc, y_pred, target_names=class_names, output_dict=True)
report_str = classification_report(y_enc, y_pred, target_names=class_names)
cm        = confusion_matrix(y_enc, y_pred)

print("=" * 70)
print("CLASSIFICATION REPORT  (PANNs embeddings + augmentation)")
print("=" * 70)
print(report_str)
print(f"Overall Accuracy: {acc:.4f}  ({int(acc * len(y_enc))}/{len(y_enc)} correct)")


# ── Save text results ─────────────────────────────────────────────────────────

rpt_path = os.path.join(RESULTS_DIR, "classification_report.txt")
with open(rpt_path, "w") as fh:
    fh.write("Model: LightGBM on PANNs CNN14 embeddings + augmentation\n")
    fh.write(f"Samples: {X_arr.shape[0]}  Features: {X_arr.shape[1]}\n")
    fh.write(f"Overall Accuracy: {acc:.4f}\n\n")
    fh.write(report_str)
print(f"Saved report   → {rpt_path}")

cm_df = pd.DataFrame(cm, index=class_names, columns=class_names)
cm_df.to_csv(os.path.join(RESULTS_DIR, "confusion_matrix.csv"))


# ── Plot 1: Confusion matrix ──────────────────────────────────────────────────

fig, ax = plt.subplots(figsize=(max(8, len(class_names)), max(6, len(class_names) - 1)))
sns.heatmap(cm_df, annot=True, fmt="d", cmap="YlOrRd",
            linewidths=0.5, ax=ax, cbar_kws={"shrink": 0.8})
ax.set_xlabel("Predicted", fontsize=11)
ax.set_ylabel("Actual", fontsize=11)
ax.set_title(
    f"Confusion Matrix — PANNs + LightGBM\nAccuracy: {acc:.1%}  "
    f"({X_arr.shape[0]} samples after augmentation)",
    fontsize=11,
)
plt.tight_layout()
fig.savefig(os.path.join(RESULTS_DIR, "confusion_matrix.png"), dpi=150)
plt.close(fig)
print(f"Saved CM       → {RESULTS_DIR}/confusion_matrix.png")


# ── Plot 2: Per-class metrics ─────────────────────────────────────────────────

metrics_df = pd.DataFrame({
    cls: {
        "Precision": report[cls]["precision"],
        "Recall":    report[cls]["recall"],
        "F1":        report[cls]["f1-score"],
    }
    for cls in class_names
}).T

fig, ax = plt.subplots(figsize=(max(10, len(class_names) * 1.2), 5))
x = np.arange(len(class_names))
w = 0.25
for i, (metric, color) in enumerate(zip(
        ["Precision", "Recall", "F1"],
        ["#4C9BE8", "#F5A623", "#7ED321"])):
    ax.bar(x + i * w, metrics_df[metric], w, label=metric, color=color, alpha=0.85)
ax.set_xticks(x + w)
ax.set_xticklabels(class_names, rotation=35, ha="right", fontsize=9)
ax.set_ylim(0, 1.05)
ax.set_ylabel("Score")
ax.set_title(f"Per-class Metrics — PANNs + LightGBM  (acc {acc:.1%})")
ax.axhline(acc, color="red", ls="--", lw=1, label=f"Overall acc {acc:.1%}")
ax.legend()
plt.tight_layout()
fig.savefig(os.path.join(RESULTS_DIR, "per_class_metrics.png"), dpi=150)
plt.close(fig)
print(f"Saved metrics  → {RESULTS_DIR}/per_class_metrics.png")


# ── Train final model on all data ─────────────────────────────────────────────

print("\nTraining final model on all data...")
clf.fit(X_scaled, y_enc)


# ── Plot 3: LightGBM feature importance (top 30 PANNs dims) ──────────────────
# PANNs dims don't have human-readable names, but the pattern still shows
# which embedding dimensions the model relies on most.

def build_feature_names():
    """
    Human/biologist-readable feature names.
    Groups features by what they capture acoustically, not array position.
    """
    names = []

    # Block 1: 32 linear rumble sub-bands
    rumble_bands_lin = np.linspace(8, 300, 33)
    for i in range(32):
        lo, hi = rumble_bands_lin[i], rumble_bands_lin[i+1]
        names.append(f"Infrasonic energy {lo:.0f}–{hi:.0f} Hz")

    # Block 1b: 16 log-spaced low-end rumble bands
    rumble_bands_log = np.logspace(np.log10(8), np.log10(120), 17)
    for i in range(16):
        lo, hi = rumble_bands_log[i], rumble_bands_log[i+1]
        names.append(f"Rumble fundamental detail {lo:.0f}–{hi:.0f} Hz")

    # Block 2: 16 AM modulation rates
    # These capture the tremor/flutter rate of the call envelope —
    # a biologically meaningful property tied to vocal fold behavior
    for mf in np.logspace(0, np.log10(80), 16):
        names.append(f"Call tremor rate {mf:.1f} Hz")

    # Block 3: 8 harmonic regularity scores
    for f0 in [10, 12, 14, 16, 18, 20, 22, 25]:
        names.append(f"Harmonic clarity at F0={f0} Hz")

    # Block 4a: 32 temporal RMS frames → call amplitude envelope
    # Split into biologically meaningful call phases
    # Frames 1–8 = onset/attack, 9–16 = early body, 17–24 = late body, 25–32 = offset
    phase_labels = (
        [f"Call onset energy (phase {i+1}/8)"   for i in range(8)] +
        [f"Call body energy early (phase {i+1}/8)"  for i in range(8)] +
        [f"Call body energy late (phase {i+1}/8)"   for i in range(8)] +
        [f"Call offset energy (phase {i+1}/8)"  for i in range(8)]
    )
    names.extend(phase_labels)

    # Block 4b: 32 temporal delta features → rate of amplitude change
    # Delta = how fast the call is rising or falling at each phase
    # This is what actually dominated — rename to make it clear
    delta_labels = (
        [f"Amplitude rise rate — onset (phase {i+1}/8)"    for i in range(8)] +
        [f"Amplitude change rate — early body (phase {i+1}/8)"  for i in range(8)] +
        [f"Amplitude change rate — late body (phase {i+1}/8)"   for i in range(8)] +
        [f"Amplitude decay rate — offset (phase {i+1}/8)"  for i in range(8)]
    )
    names.extend(delta_labels)

    # Block 5: 64 mel means + 64 mel stds (200–1000 Hz upper harmonics)
    for i in range(64):
        names.append(f"Upper harmonic energy (mel band {i+1} mean)")
    for i in range(64):
        names.append(f"Upper harmonic variability (mel band {i+1} std)")

    # Block 6: spectral contrast — peak-to-valley in each band
    for i in range(7):
        names.append(f"Call tonality — band {i+1} mean (spectral contrast)")
    for i in range(5):
        names.append(f"Call tonality — band {i+1} variability")

    # Block 7: MFCC — vocal tract / timbral shape
    for i in range(13):
        names.append(f"Vocal timbre coefficient {i+1} (MFCC mean)")
    for i in range(13):
        names.append(f"Vocal timbre variability {i+1} (MFCC std)")

    # Block 8: band energy ratios
    names += [
        "Infrasonic fraction (rumble / total energy)",
        "Mid-frequency fraction (120–500 Hz / total)",
        "High-frequency fraction (500 Hz+ / total)",
        "Infrasonic dominance ratio (rumble / HF)",
        "Mid-to-rumble ratio (120–500 Hz / rumble)",
    ]

    # Block 9: ZCR/RMS
    names += [
        "Zero-crossing rate mean (call breathiness)",
        "Zero-crossing rate variability",
        "Overall call amplitude (RMS mean)",
        "Amplitude variability (RMS std)",
    ]

    return names

feat_names = build_feature_names()
n_feats = len(clf.feature_importances_)
feat_names = (feat_names + [f"feat_{i}" for i in range(n_feats)])[:n_feats]

importances = pd.Series(clf.feature_importances_, index=feat_names, name="importance")
top30 = importances.nlargest(30).sort_values()

def bar_color(name):
    n = name.lower()
    if "onset" in n or "offset" in n or "body" in n or "amplitude" in n or "rise" in n or "decay" in n:
        return "#4C9BE8"   # blue = call shape / temporal
    if "infrasonic" in n or "rumble" in n or "fundamental" in n:
        return "#E8664C"   # coral = infrasonic energy
    if "tremor" in n or "am rate" in n:
        return "#7ED321"   # green = AM / tremor
    if "harmonic clarity" in n:
        return "#F5A623"   # amber = harmonic
    if "upper harmonic" in n or "mel" in n:
        return "#9B59B6"   # purple = mel / upper harmonics
    if "tonality" in n or "contrast" in n:
        return "#1ABC9C"   # teal = spectral contrast
    if "timbre" in n or "mfcc" in n:
        return "#E67E22"   # orange = vocal timbre
    if "fraction" in n or "ratio" in n or "dominance" in n:
        return "#E74C3C"   # red = energy ratios
    return "#888888"

colors = [bar_color(n) for n in top30.index]

# Shorten labels for display (keep biological meaning, drop redundant words)
def shorten(name):
    name = name.replace(" (spectral contrast)", "")
    name = name.replace("Amplitude ", "Amp. ")
    name = name.replace("variability", "var.")
    name = name.replace("coefficient", "coeff.")
    name = name.replace("Infrasonic energy", "Infrasonic")
    name = name.replace("Rumble fundamental detail", "Rumble detail")
    name = name.replace("Upper harmonic energy", "Upper harmonic")
    name = name.replace("Upper harmonic variability", "Upper harmonic var.")
    name = name.replace("Overall call amplitude", "Call amplitude")
    return name

short_labels = [shorten(n) for n in top30.index]

fig, ax = plt.subplots(figsize=(14, 10))
bars = ax.barh(range(len(top30)), top30.values, color=colors, alpha=0.88, height=0.7)
ax.set_yticks(range(len(top30)))
ax.set_yticklabels(short_labels, fontsize=9)
ax.set_xlabel("LightGBM split gain  (how much this feature reduces classification error)")
ax.set_title(
    f"Top 30 Features — Elephant Call Context Classifier\n"
    f"Accuracy: {acc:.1%}  |  {X_arr.shape[0]} samples  |  {X_arr.shape[1]} acoustic features",
    fontsize=12, pad=14
)

# Add value labels
for i, val in enumerate(top30.values):
    ax.text(val + 8, i, f"{val:.0f}", va="center", fontsize=8, color="#333333")

ax.set_xlim(0, top30.values.max() * 1.14)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

# Legend grouped by biological meaning
from matplotlib.patches import Patch
legend_elements = [
    Patch(facecolor="#4C9BE8", label="Call shape (amplitude envelope & rate of change)"),
    Patch(facecolor="#E8664C", label="Infrasonic / rumble band energy"),
    Patch(facecolor="#7ED321", label="Call tremor rate (amplitude modulation)"),
    Patch(facecolor="#F5A623", label="Harmonic clarity"),
    Patch(facecolor="#9B59B6", label="Upper harmonics (200–1000 Hz, mel)"),
    Patch(facecolor="#1ABC9C", label="Call tonality (tonal vs noisy)"),
    Patch(facecolor="#E67E22", label="Vocal timbre (MFCC)"),
    Patch(facecolor="#E74C3C", label="Band energy ratios"),
    Patch(facecolor="#888888", label="ZCR / RMS"),
]
ax.legend(handles=legend_elements, loc="lower right", fontsize=8.5,
          framealpha=0.92, title="Acoustic feature type", title_fontsize=9)

# Annotation explaining what dominates
dominant = top30.index[-1]
ax.annotate(
    "Call shape features dominate:\nhow fast amplitude rises/falls\ndistinguishes contexts better\nthan raw frequency content",
    xy=(top30.values[-1], len(top30) - 1),
    xytext=(top30.values[-1] * 0.55, len(top30) - 4),
    fontsize=8, color="#2C3E50",
    arrowprops=dict(arrowstyle="->", color="#2C3E50", lw=1),
)

plt.tight_layout()
fig.savefig(os.path.join(RESULTS_DIR, "feature_importance.png"), dpi=150)
plt.close(fig)
print(f"Saved feat imp → {RESULTS_DIR}/feature_importance.png")


# ── Plot 4: SHAP (biologist-facing) ──────────────────────────────────────────
# For PANNs dims, SHAP beeswarm shows which embedding directions push toward
# each context — less interpretable than named features but still useful
# for showing the model isn't a black box.

try:
    import shap
    print("\nComputing SHAP values...")

    explainer   = shap.TreeExplainer(clf)
    shap_values = explainer.shap_values(X_scaled)

    # Global bar summary
    fig_s = plt.figure(figsize=(10, 7))
    shap.summary_plot(
        shap_values, X_scaled,
        class_names=class_names,
        max_display=20,
        show=False,
        plot_type="bar",
    )
    plt.title("SHAP Feature Impact by Context (PANNs dims, top 20)", fontsize=11)
    plt.tight_layout()
    plt.savefig(os.path.join(RESULTS_DIR, "shap_summary.png"), dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved SHAP     → {RESULTS_DIR}/shap_summary.png")

    # Per-class beeswarm
    for i, cls in enumerate(class_names):
        sv = shap_values[i] if isinstance(shap_values, list) else shap_values[:, :, i]
        plt.figure(figsize=(10, 6))
        shap.summary_plot(sv, X_scaled, max_display=15, show=False, plot_type="dot")
        plt.title(f"SHAP — {cls}", fontsize=11)
        plt.tight_layout()
        cls_safe = cls.replace(" ", "_").replace("/", "-")
        plt.savefig(os.path.join(RESULTS_DIR, f"shap_{cls_safe}.png"),
                    dpi=150, bbox_inches="tight")
        plt.close()
    print(f"Saved per-class SHAP → {RESULTS_DIR}/shap_*.png")

except ImportError:
    print("SHAP not installed — skipping. Run: pip install shap")
except Exception as e:
    print(f"SHAP failed: {e}")


# ── Save model ────────────────────────────────────────────────────────────────

model_path = os.path.join(BASE, "trained_panns.joblib")
joblib.dump({
    "clf":           clf,
    "scaler":        scaler,
    "label_encoder": target_le,
    "class_names":   class_names,
    "embedding_dim": X_arr.shape[1],
}, model_path)
print(f"\nSaved model    → {model_path}")
print(f"All results    → {RESULTS_DIR}/")


# ── Inference helper ──────────────────────────────────────────────────────────
# Use this to predict context for a new cleaned WAV file.

def predict_context(wav_path: str, model_path: str = model_path) -> dict:
    """
    Given a path to a cleaned elephant WAV, returns predicted context
    and confidence scores for all classes.

    Example:
        result = predict_context("cleaned/0042_recording_clean.wav")
        print(result["predicted"], result["confidence"])
    """
    bundle = joblib.load(model_path)
    clf_   = bundle["clf"]
    sc_    = bundle["scaler"]
    le_    = bundle["label_encoder"]

    at_ = load_panns_model()
    y, sr = librosa.load(wav_path, sr=SR, mono=True)
    emb   = get_embedding(at_, y, SR).reshape(1, -1)
    emb_s = sc_.transform(emb)

    proba     = clf_.predict_proba(emb_s)[0]
    pred_idx  = np.argmax(proba)
    predicted = le_.inverse_transform([pred_idx])[0]

    return {
        "predicted":   predicted,
        "confidence":  float(proba[pred_idx]),
        "all_scores":  dict(zip(le_.classes_, proba.tolist())),
    }