"""
Elephant vocalization classifier — improved from 67% baseline.

Key changes vs original:
  1. Elephant-specific features instead of MFCCs/chroma/tonnetz
     - Sub-band energies at 5/20/100/300/1000 Hz boundaries
     - F0 contour shape (slope, curvature, modulation rate)
     - Harmonicity ratio (HNR) — how tonal vs noisy the call is
     - Call onset/offset energy asymmetry
  2. SMOTE oversampling to fix class imbalance before training
  3. Gradient Boosting ensemble (XGBoost + RF) — better than RF alone
  4. Feature scaling before SMOTE and GBM
  5. Consistent feature set between training and prediction

Requirements:
    pip install librosa scikit-learn imbalanced-learn xgboost numpy pandas
"""

import os
import warnings
import numpy as np
import pandas as pd
import librosa
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline

try:
    from xgboost import XGBClassifier
    HAS_XGB = True
except ImportError:
    HAS_XGB = False
    print("XGBoost not installed. Install with: pip install xgboost")

try:
    from lightgbm import LGBMClassifier
    HAS_LGB = True
except ImportError:
    HAS_LGB = False
    print("LightGBM not installed. Install with: pip install lightgbm")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import joblib

warnings.filterwarnings("ignore")

BASE        = os.path.dirname(os.path.abspath(__file__))
DATA_DIR    = os.path.join(BASE, "data")
SEG_DIR     = os.path.join(DATA_DIR, "segmented")
RESULTS_DIR = os.path.join(BASE, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# Elephant frequency bands — same as predict.py for consistency
BANDS = {
    "infrasonic": (5,   20),
    "rumble":     (20,  100),
    "low_call":   (100, 300),
    "mid_call":   (300, 1000),
    "trumpet":    (1000, 4000),
}

SR = 22050
N_FFT = 4096
HOP   = 1024


# ── Feature extraction ────────────────────────────────────────────────────────

def band_energy(S_power, freqs, lo, hi):
    mask = (freqs >= lo) & (freqs < hi)
    return float(np.mean(S_power[mask])) if mask.any() else 0.0

def band_ratio(S_power, freqs, lo, hi):
    total = float(np.mean(S_power))
    return band_energy(S_power, freqs, lo, hi) / total if total > 1e-12 else 0.0


def extract_features(filepath, sr=SR):
    try:
        y, sr = librosa.load(filepath, sr=sr, mono=True)
    except Exception:
        return None
    if len(y) < sr * 0.05:
        return None

    f = {}
    f["duration"] = len(y) / sr

    # ── Spectrogram ───────────────────────────────────────────────────────────
    S     = np.abs(librosa.stft(y, n_fft=N_FFT, hop_length=HOP))
    S_pow = S ** 2
    freqs = librosa.fft_frequencies(sr=sr, n_fft=N_FFT)

    # ── Elephant band energies and ratios ─────────────────────────────────────
    for name, (lo, hi) in BANDS.items():
        f[f"energy_{name}"]  = band_energy(S_pow, freqs, lo, hi)
        f[f"ratio_{name}"]   = band_ratio(S_pow, freqs, lo, hi)

    # Low-to-high energy ratio — key discriminator (rumbles are bottom-heavy)
    low_e  = band_energy(S_pow, freqs, 5,   300)
    high_e = band_energy(S_pow, freqs, 300, 4000)
    f["low_high_ratio"] = low_e / (high_e + 1e-12)

    # ── F0 contour features ───────────────────────────────────────────────────
    # pyin is best for low-frequency pitch tracking
    f0, voiced, _ = librosa.pyin(y, fmin=10, fmax=2000, sr=sr,
                                  frame_length=N_FFT)
    f0v = f0[voiced] if voiced is not None else f0[~np.isnan(f0)]

    if len(f0v) >= 4:
        f["pitch_mean"]     = float(np.mean(f0v))
        f["pitch_std"]      = float(np.std(f0v))
        f["pitch_min"]      = float(np.min(f0v))
        f["pitch_max"]      = float(np.max(f0v))
        f["pitch_range"]    = float(np.ptp(f0v))
        f["pitch_median"]   = float(np.median(f0v))
        f["voiced_fraction"]= float(np.sum(voiced) / len(voiced))

        # Contour shape — is the call rising, falling, or flat?
        t = np.arange(len(f0v))
        slope, intercept = np.polyfit(t, f0v, 1)
        f["pitch_slope"]    = float(slope)          # + = rising, - = falling

        # Curvature — is it a U-shape or arch?
        if len(f0v) >= 6:
            coeffs = np.polyfit(t, f0v, 2)
            f["pitch_curvature"] = float(coeffs[0])
        else:
            f["pitch_curvature"] = 0.0

        # Modulation rate — how fast is pitch varying? (trill vs smooth)
        diffs = np.diff(f0v)
        f["pitch_modulation"] = float(np.std(diffs))

        # First half vs second half mean — call shape asymmetry
        mid = len(f0v) // 2
        f["pitch_first_half"]  = float(np.mean(f0v[:mid]))
        f["pitch_second_half"] = float(np.mean(f0v[mid:]))
        f["pitch_asymmetry"]   = f["pitch_second_half"] - f["pitch_first_half"]
    else:
        for k in ["pitch_mean", "pitch_std", "pitch_min", "pitch_max",
                   "pitch_range", "pitch_median", "voiced_fraction",
                   "pitch_slope", "pitch_curvature", "pitch_modulation",
                   "pitch_first_half", "pitch_second_half", "pitch_asymmetry"]:
            f[k] = 0.0

    # ── Harmonicity (HNR proxy) ───────────────────────────────────────────────
    # Spectral contrast measures tonal peaks vs valleys — high = more harmonic
    contrast = librosa.feature.spectral_contrast(y=y, sr=sr, n_bands=6,
                                                  fmin=20.0)
    for i in range(contrast.shape[0]):
        f[f"contrast_{i}_mean"] = float(np.mean(contrast[i]))
        f[f"contrast_{i}_std"]  = float(np.std(contrast[i]))
    f["harmonicity_mean"] = float(np.mean(contrast))  # overall tonal strength

    # ── Spectral shape ────────────────────────────────────────────────────────
    cent = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    f["centroid_mean"] = float(np.mean(cent))
    f["centroid_std"]  = float(np.std(cent))

    bw = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]
    f["bandwidth_mean"] = float(np.mean(bw))
    f["bandwidth_std"]  = float(np.std(bw))

    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, roll_percent=0.85)[0]
    f["rolloff_mean"] = float(np.mean(rolloff))
    f["rolloff_std"]  = float(np.std(rolloff))

    flatness = librosa.feature.spectral_flatness(y=y)[0]
    f["flatness_mean"] = float(np.mean(flatness))
    f["flatness_std"]  = float(np.std(flatness))

    # ── Temporal / energy envelope ────────────────────────────────────────────
    rms = librosa.feature.rms(y=y)[0]
    f["rms_mean"]  = float(np.mean(rms))
    f["rms_std"]   = float(np.std(rms))
    f["rms_max"]   = float(np.max(rms))

    # Onset vs offset energy — does the call build up or die away?
    n3 = len(rms) // 3
    if n3 > 0:
        f["energy_onset"]  = float(np.mean(rms[:n3]))
        f["energy_middle"] = float(np.mean(rms[n3:2*n3]))
        f["energy_offset"] = float(np.mean(rms[2*n3:]))
        f["energy_shape"]  = f["energy_offset"] - f["energy_onset"]
    else:
        f["energy_onset"] = f["energy_middle"] = f["energy_offset"] = f["energy_shape"] = 0.0

    zcr = librosa.feature.zero_crossing_rate(y)[0]
    f["zcr_mean"] = float(np.mean(zcr))
    f["zcr_std"]  = float(np.std(zcr))

    tempo = librosa.feature.tempo(y=y, sr=sr)[0]
    f["tempo"] = float(np.atleast_1d(tempo)[0])

    return f


# ── Load & merge ──────────────────────────────────────────────────────────────

print("Loading data...")
data = pd.read_csv(os.path.join(DATA_DIR, "data.csv"))
data = data.drop_duplicates(subset="file_name")

segments = pd.read_csv(os.path.join(DATA_DIR, "segments.csv"))
segments.columns = segments.columns.str.strip()
segments["file_name_key"] = segments["original_file_name"].str.replace(".wav", "", regex=False)

existing = set(os.listdir(SEG_DIR))
segments = segments[segments["segment_file_name"].isin(existing)]

merged = segments.merge(data, left_on="file_name_key", right_on="file_name", how="inner")
merged = merged.dropna(subset=["context"])

# Keep classes with >= 3 samples
counts = merged["context"].value_counts()
merged = merged[merged["context"].isin(counts[counts >= 3].index)].reset_index(drop=True)

print(f"Usable segments: {len(merged)}")
print(merged["context"].value_counts().to_string())
print()

# ── Extract features ──────────────────────────────────────────────────────────

print("Extracting elephant-specific audio features...")
audio_rows, valid_idx = [], []
for idx, row in merged.iterrows():
    path = os.path.join(SEG_DIR, row["segment_file_name"])
    feats = extract_features(path)
    if feats:
        audio_rows.append(feats)
        valid_idx.append(idx)
    if len(audio_rows) % 50 == 0 and len(audio_rows) > 0:
        print(f"  {len(audio_rows)} / {len(merged)}")

audio_df = pd.DataFrame(audio_rows, index=valid_idx)
merged   = merged.loc[valid_idx]
print(f"Extracted features for {len(audio_df)} segments\n")

# ── Metadata features ─────────────────────────────────────────────────────────

META_COLS = ["name", "age", "gender"]
meta_enc  = pd.DataFrame(index=merged.index)
for col in META_COLS:
    le = LabelEncoder()
    meta_enc[col] = le.fit_transform(merged[col].fillna("Unknown"))
    print(f"  {col}: {list(le.classes_)}")
print()

# ── Feature matrix ────────────────────────────────────────────────────────────

X = pd.concat([audio_df.reset_index(drop=True),
               meta_enc.reset_index(drop=True)], axis=1).fillna(0)
feat_names = list(X.columns)
X_arr = X.values.astype(np.float64)

target_le = LabelEncoder()
y = target_le.fit_transform(merged["context"].values)
class_names = list(target_le.classes_)

print(f"Feature matrix: {X_arr.shape[0]} samples × {X_arr.shape[1]} features")
print(f"Classes: {class_names}\n")

# ── Build classifiers ─────────────────────────────────────────────────────────

rf = RandomForestClassifier(
    n_estimators=500,
    max_depth=None,
    min_samples_leaf=2,
    max_features="sqrt",
    class_weight="balanced_subsample",
    random_state=42,
    n_jobs=-1,
)

estimators = [("rf", rf)]
clf_parts  = ["RF"]

if HAS_XGB:
    xgb = XGBClassifier(
        n_estimators=400,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        use_label_encoder=False,
        eval_metric="mlogloss",
        random_state=42,
        n_jobs=-1,
    )
    estimators.append(("xgb", xgb))
    clf_parts.append("XGBoost")

if HAS_LGB:
    # LightGBM — leaf-wise growth, different inductive bias to RF & XGB
    # is_unbalance handles class weights natively without SMOTE interaction issues
    lgb = LGBMClassifier(
        n_estimators=400,
        max_depth=-1,
        learning_rate=0.05,
        num_leaves=63,
        subsample=0.8,
        colsample_bytree=0.8,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
        verbose=-1,
    )
    estimators.append(("lgb", lgb))
    clf_parts.append("LightGBM")

if not HAS_XGB and not HAS_LGB:
    gb = GradientBoostingClassifier(
        n_estimators=300, max_depth=4, learning_rate=0.05,
        subsample=0.8, random_state=42,
    )
    estimators.append(("gb", gb))
    clf_parts.append("GradientBoosting")

clf_name = " + ".join(clf_parts) + " Ensemble"
ensemble  = VotingClassifier(estimators=estimators, voting="soft", n_jobs=-1)

# ── SMOTE + cross-validation ──────────────────────────────────────────────────

n_splits = max(2, min(5, int(merged["context"].value_counts().min())))
print(f"Cross-validation: {n_splits}-fold stratified + SMOTE\n")
cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)

smote_k  = max(1, min(5, merged["context"].value_counts().min() - 1))
pipeline = ImbPipeline([
    ("scaler", StandardScaler()),
    ("smote",  SMOTE(k_neighbors=smote_k, random_state=42)),
    ("clf",    ensemble),
])

print(f"Training {clf_name} with SMOTE (k={smote_k})...")
y_pred = cross_val_predict(pipeline, X_arr, y, cv=cv)

# ── Results ───────────────────────────────────────────────────────────────────

acc    = accuracy_score(y, y_pred)
report = classification_report(y, y_pred, target_names=class_names, output_dict=True)
report_str = classification_report(y, y_pred, target_names=class_names)
cm     = confusion_matrix(y, y_pred)

print("\n" + "=" * 70)
print("CLASSIFICATION REPORT")
print("=" * 70)
print(report_str)

print("=" * 70)
print("CONFUSION MATRIX")
print("=" * 70)
cm_df = pd.DataFrame(cm, index=class_names, columns=class_names)
print(cm_df.to_string())
print(f"\nOverall Accuracy: {acc:.4f}  ({int(acc*len(y))}/{len(y)} correct)")

# ── Save text results ─────────────────────────────────────────────────────────

report_path = os.path.join(RESULTS_DIR, "classification_report.txt")
with open(report_path, "w") as fh:
    fh.write(f"Model: {clf_name}\n")
    fh.write(f"Overall Accuracy: {acc:.4f}  ({int(acc*len(y))}/{len(y)} correct)\n\n")
    fh.write(report_str)
print(f"\nSaved report   → {report_path}")

cm_csv = os.path.join(RESULTS_DIR, "confusion_matrix.csv")
cm_df.to_csv(cm_csv)
print(f"Saved CM csv   → {cm_csv}")

# ── Plot 1: Confusion matrix heatmap ─────────────────────────────────────────

fig, ax = plt.subplots(figsize=(max(8, len(class_names)), max(6, len(class_names) - 1)))
sns.heatmap(cm_df, annot=True, fmt="d", cmap="Blues",
            linewidths=0.5, ax=ax, cbar_kws={"shrink": 0.8})
ax.set_xlabel("Predicted", fontsize=11)
ax.set_ylabel("Actual", fontsize=11)
ax.set_title(f"Confusion Matrix — {clf_name}\nAccuracy: {acc:.1%}", fontsize=12)
plt.tight_layout()
cm_plot = os.path.join(RESULTS_DIR, "confusion_matrix.png")
fig.savefig(cm_plot, dpi=150)
plt.close(fig)
print(f"Saved CM plot  → {cm_plot}")

# ── Plot 2: Per-class precision / recall / F1 bar chart ──────────────────────

metrics_df = pd.DataFrame({
    cls: {
        "Precision": report[cls]["precision"],
        "Recall":    report[cls]["recall"],
        "F1":        report[cls]["f1-score"],
    }
    for cls in class_names
}).T

fig, ax = plt.subplots(figsize=(max(10, len(class_names) * 1.2), 5))
x    = np.arange(len(class_names))
w    = 0.25
colors = ["#4C9BE8", "#F5A623", "#7ED321"]
for i, (metric, color) in enumerate(zip(["Precision", "Recall", "F1"], colors)):
    ax.bar(x + i * w, metrics_df[metric], w, label=metric, color=color, alpha=0.85)
ax.set_xticks(x + w)
ax.set_xticklabels(class_names, rotation=35, ha="right", fontsize=9)
ax.set_ylim(0, 1.05)
ax.set_ylabel("Score")
ax.set_title(f"Per-class Metrics — {clf_name}")
ax.axhline(acc, color="red", linestyle="--", linewidth=1, label=f"Overall acc {acc:.1%}")
ax.legend()
plt.tight_layout()
metrics_plot = os.path.join(RESULTS_DIR, "per_class_metrics.png")
fig.savefig(metrics_plot, dpi=150)
plt.close(fig)
print(f"Saved metrics  → {metrics_plot}")

# ── Train final model & feature importances ───────────────────────────────────

print("\nTraining final model on all data...")
pipeline.fit(X_arr, y)

rf_fitted   = pipeline.named_steps["clf"].estimators_[0]
importances = pd.Series(rf_fitted.feature_importances_, index=feat_names)
importances = importances.sort_values(ascending=False)

print("\n" + "=" * 70)
print("TOP 20 FEATURE IMPORTANCES (Random Forest component)")
print("=" * 70)
print(importances.head(20).to_string())

# ── Plot 3: Feature importance bar chart ─────────────────────────────────────

top20 = importances.head(20)
fig, ax = plt.subplots(figsize=(9, 6))
top20.sort_values().plot.barh(ax=ax, color="#4C9BE8", alpha=0.85)
ax.set_xlabel("Importance")
ax.set_title("Top 20 Feature Importances (RF component)")
plt.tight_layout()
imp_plot = os.path.join(RESULTS_DIR, "feature_importance.png")
fig.savefig(imp_plot, dpi=150)
plt.close(fig)
print(f"Saved feat imp → {imp_plot}")

# ── Plot 4: Class distribution ────────────────────────────────────────────────

fig, ax = plt.subplots(figsize=(max(8, len(class_names)), 4))
counts_series = merged["context"].value_counts()
counts_series.plot.bar(ax=ax, color="#7ED321", alpha=0.85)
ax.set_ylabel("Samples")
ax.set_title("Class Distribution in Training Data")
ax.set_xticklabels(ax.get_xticklabels(), rotation=35, ha="right")
plt.tight_layout()
dist_plot = os.path.join(RESULTS_DIR, "class_distribution.png")
fig.savefig(dist_plot, dpi=150)
plt.close(fig)
print(f"Saved class dist → {dist_plot}")

# ── Save importances CSV ──────────────────────────────────────────────────────

imp_csv = os.path.join(RESULTS_DIR, "feature_importances.csv")
importances.reset_index().rename(columns={"index": "feature", 0: "importance"}).to_csv(imp_csv, index=False)
print(f"Saved feat csv → {imp_csv}")

# ── Save trained pipeline ─────────────────────────────────────────────────────

model_path = os.path.join(BASE, "trained_pipeline.joblib")
joblib.dump({
    "pipeline":       pipeline,
    "label_encoder":  target_le,
    "feature_names":  feat_names,
    "class_names":    class_names,
}, model_path)
print(f"\nSaved model    → {model_path}")
print(f"\nAll results in → {RESULTS_DIR}/")
print("  confusion_matrix.png")
print("  per_class_metrics.png")
print("  feature_importance.png")
print("  class_distribution.png")
print("  classification_report.txt")
print("  confusion_matrix.csv")
print("  feature_importances.csv")