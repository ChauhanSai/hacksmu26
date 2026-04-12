# Elephant Linguistics — CLAUDE.md

## What This Is
A computational bioacoustics pipeline that analyzes elephant vocalizations to decode behavioral meaning. **Not a translator** — a behavioral correlation engine that maps acoustic profiles to observed behaviors with confidence scores.

## Data Source
Google Cloud Storage — segmented `.wav` files + metadata CSV/JSON per call.

**Metadata fields:** `filename`, `context` (~20 behavioral categories), `age_sex`, `body_part`, `comm_mode`, `sound_type`, `elephant_id`, `receiver_id`, `country`, `session_id`

**Auth:** `export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"`

## Pipeline: 6 Stages

```
Audio + metadata → [1] Feature Extraction → [2] Normalize + Cluster (GMM)
→ [3] Statistical Analysis (PMI) → [4] Classification (RF) → [5] Inference → [6] Visualization
```

---

## Stage 1: Feature Extraction (20 features per call)

**Deps:** `numpy scipy librosa parselmouth scikit-learn gensim umap-learn matplotlib seaborn pandas`

Use `parselmouth` (Praat wrapper) for pitch/formants — handles infrasonic frequencies better than librosa.

| # | Feature | Notes |
|---|---------|-------|
| 1-4 | `mean_f0`, `std_f0`, `f0_slope`, `f0_range` | **CRITICAL:** `pitch_floor=5, pitch_ceiling=100` (default is 75-600 Hz for humans, misses elephants) |
| 5-7 | `mean_f1`, `mean_f2`, `mean_f3` | **CRITICAL:** `maximum_formant=500` (default 5500 Hz is for humans) |
| 8-10 | `duration`, `attack_time`, `temporal_centroid` | Temporal shape |
| 11-13 | `rms_energy`, `mean_hnr`, `spectral_flatness` | Energy/noise |
| 14-16 | `spectral_centroid`, `spectral_bandwidth`, `spectral_rolloff` | Spectral shape |
| 17-20 | `mfcc_1` to `mfcc_4` | **CRITICAL:** `fmin=5, fmax=500`, `n_fft=8192` |

**Key function:** `extract_features(y_segment, sr) → dict of 20 features`

**Batch:** `process_all_calls(audio_dir, metadata_df) → feature_matrix, feature_names, metadata`

---

## Stage 2: Normalization & Clustering

1. **StandardScaler** on all 20 features
2. **Age/sex normalization** on F0 features within groups (prevent body-size clustering)
3. **GMM clustering** (not k-means — soft probabilistic assignments)
   - BIC to find optimal `k` (range 5–50)
   - `covariance_type='full'`
   - Output: `labels` (hard), `probabilities` (soft, shape N×k)
4. **Vowel clustering:** separate GMM on `(mean_f1, mean_f2)` with `n_components=5`

---

## Stage 3: Statistical Analysis

- **Symbol sequences:** group calls by `session_id`
- **Unigram probs:** frequency of each symbol
- **PMI matrix** `(n_symbols × n_contexts)`: high PMI (>2.0) = strong behavioral association → primary decoding signal
- **Transition matrix** `(n_symbols × n_symbols)`: row entropy — low = syntactic constraint
- **Regional variation:** chi-squared per symbol across countries (universal vs. learned)
- **Name detection:** symbols directed >75% at single receiver = individual "name" candidates
- **Herd inference:** Louvain community detection on session co-occurrence graph (requires `networkx`)

---

## Stage 4: Classification

Three `RandomForestClassifier(n_estimators=200, class_weight='balanced')`:

| Classifier | Target | Labels |
|-----------|--------|--------|
| `context_clf` | Behavioral context (~20 classes) | From metadata |
| `valence_clf` | positive / negative / neutral | Mapped from context |
| `arousal_clf` | high / medium / low | Mapped from context |

Use 80/20 split + 5-fold CV. Feature importances reveal which acoustic features carry meaning.

**Valence map:** Affiliative/Courtship/Coalition → positive; Aggressive/Distress/Death → negative; rest → neutral  
**Arousal map:** Aggressive/Birth/Death/Distress → high; Affiliative/Foraging/Maintenance → low; rest → medium

---

## Stage 5b: Advanced Inference (`advanced_inference.py`)

Extends Stage 5 with caller identification and enriched context prediction:

| Function | Purpose |
|---|---|
| `train_caller_classifier` | RandomForest predicting `elephant_id` from acoustics — requires ≥3 calls per caller |
| `build_voice_profiles` | Per-elephant feature means/stds (acoustic fingerprint) |
| `caller_identifiability` | Score each elephant by between/within-distance ratio — who has the most distinct voice |
| `build_enhanced_features` | One-hot encode `age_sex`, `body_part`, `comm_mode`, `sound_type` + append to acoustic features |
| `train_enhanced_context` | GradientBoosting context classifier on augmented features |
| `caller_context_affinity` | Chi² test per elephant vs population — identifies "specialist" callers |
| `CallSimilaritySearch` | k-NN for acoustic nearest-neighbor retrieval |
| `full_call_inference` | Combined **who + what + why** report per call with top-3 predictions |

---

## Stage 5: Inference Generation

**`build_meaning_vector(feature_vector_scaled, metadata_row, ...) → dict`** with:
- `symbol`, `cluster_confidence`
- `top_context`, `context_confidence`, `alt_context`, `alt_confidence`
- `valence`, `arousal`, `caller_age_sex`, `body_part`, `comm_mode`, `directed_at`
- `context_probabilities` (full dict)

**`generate_interpretation(meaning_vector) → {interpretation, confidence, alternative}`**
- Uses `INTERPRETATION_TEMPLATES` dict (one per behavioral context)
- Applies modifiers for age/sex, arousal, body part, directed-at

**Output format per call:** symbol, caller info, interpretation sentence, confidence %, alternative, valence/arousal, context probability breakdown.

---

## Stage 6: High-Level Reports

- **Repertoire report:** N distinct call types, per-symbol top association + PMI + count
- **Emotion report:** top 5 acoustic features for valence and arousal prediction
- **Confusion matrix:** acoustically indistinguishable behavior pairs
- **Visualizations:** PMI heatmap, F1/F2 vowel plot, UMAP of feature space, transition matrix heatmap

---

## Critical Constants (Never Change)

```python
pitch_floor = 5          # Hz — infrasonic lower bound
pitch_ceiling = 100      # Hz
maximum_formant = 500    # Hz — elephant vocal tract
fmin = 5                 # Hz — MFCC filterbank
fmax = 500               # Hz
n_fft = 8192             # large window for low-freq resolution
```

## Behavioral Context Labels (20 categories)
Advertisement & Attraction, Affiliative, Aggressive, Ambivalent, Attacking & Mobbing, Attentive, Avoidance, Birth, Calf Nourishment & Weaning, Calf Reassurance & Protection, Coalition Building, Conflict & Confrontation, Courtship, Death, Foraging & Comfort Technique, Lone & Object Play, Maintenance, Protest & Distress

---

## Frontend (`../../frontend/`)

Vanilla HTML + Tailwind CDN + Plotly. **No React build step** — every file is static and served with `python -m http.server`.

### Design system — "Pachyderm Intelligence Terminal"

Premium dark institutional aesthetic modeled after Bloomberg Terminal × modern glassmorphism. **Every new UI element must conform.**

**Surfaces:** near-black `#07090c` base, glassy panels (`rgba(18,24,32,0.55)` + `backdrop-filter: blur(14px)`), thin low-opacity borders (`rgba(255,255,255,0.07)`), rounded-2xl (`16px`).

**Typography:** `Geist` (sans, from Google Fonts) + `Geist Mono` for numerics, labels, KPIs. Uppercase labels at `10.5px / letter-spacing 0.14em` for headers.

**Palette (CSS vars in `css/styles.css`):**
| Var | Hex | Use |
|---|---|---|
| `--risk-low`  | `#4ade80` | muted green — low / positive / affiliative |
| `--risk-med`  | `#fbbf24` | amber — medium arousal / neutral |
| `--risk-high` | `#fb923c` | orange — high arousal |
| `--risk-crit` | `#ef4444` | red — distress / avoidance / aggression |
| `--accent`    | `#7dd3fc` | icy cyan — neutral data / interaction accent |

**Never** introduce loud rainbow gradients or saturated consumer-app colors. Chart `PALETTE` in `js/charts.js` leads with cyan and uses only these risk/accent hues.

### File map

| File | Purpose |
|---|---|
| `index.html` | Home — scroll-expand hero (vanilla JS port, no React) |
| `analysis.html` | Analysis dashboard: KPI strip + 8 numbered panels |
| `GUIDE.md` | Plain-English reader's guide for every chart/panel |
| `css/styles.css` | Full design system — CSS vars, cards, tables, hero, explain mode |
| `js/hero.js` | Scroll-expand logic for home page (wheel + touch hijack until media fills) |
| `js/charts.js` | Plotly dark-theme chart builders (1 per panel) |
| `js/app.js` | Bootstrap: loads JSON from `frontend/data/`, builds KPIs, tables, interpretation cards |
| `js/explain.js` | Explain-mode toggle — hover any `[data-explain]` element for a simplified description |
| `data/*.json` | Written by `backend/elephant_linguistics/export_frontend.py` — see `frontend/data/README.md` |

### Dashboard panel order (analysis.html)

1. **Repertoire Atlas** (UMAP scatter) — full width
2. **Symbol × Context PMI Matrix** (heatmap)
3. **Sequential Transitions** (heatmap)
4. **Vowel Space F1/F2** (scatter)
5. **Behavioral Context Distribution** (bar)
6. **Voice Fingerprints** (table)
7. **Caller → Context Affinity** (table)
8. **Intelligence Briefings** — sample call interpretation cards — full width

The *Caller Identifiability Ranking* panel and the *Context Accuracy* KPI have been intentionally removed. Do not re-add them without explicit request.

### Explain mode

Click the **EXPLAIN** button in the top bar → body gets `.explain-mode` class → every `[data-explain]` element shows a cyan dashed outline on hover and a floating tooltip with the attribute value. Plotly charts simultaneously swap their hover templates to one-line plain-English sentences (≤50 chars). New panels must add `data-explain="<plain description>"`.

### Running

```bash
# Run pipeline first (populates frontend/data/)
cd backend/elephant_linguistics
python generate_sample_data.py
python run_from_csv.py --csv sample_data/features.csv

# Serve the frontend (must be HTTP — fetch() won't work with file://)
cd ../../frontend
python -m http.server 8000
# → http://localhost:8000/index.html
```
