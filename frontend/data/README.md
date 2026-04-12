# Frontend data folder

This folder is auto-populated by the backend pipeline. After running:

```bash
cd backend/elephant_linguistics
python generate_sample_data.py
python run_from_csv.py --csv sample_data/features.csv
```

the following files will appear here:

| File | Purpose |
|---|---|
| `summary.json` | Top-bar stat chips |
| `clusters.json` | UMAP 2D coords + hulls for the main scatter |
| `pmi_matrix.json` | Symbol × context PMI heatmap data |
| `transition_matrix.json` | Call-to-call transition probs |
| `vowel_space.json` | F1/F2 points for the vowel scatter |
| `context_distribution.json` | Per-context call counts |
| `caller_identifiability.json` | Top 15 most distinctive elephants |
| `voice_profiles.json` | Per-elephant acoustic averages |
| `caller_affinity.json` | Specialist caller table |
| `sample_interpretations.json` | First 8 full WHO/WHAT/WHY predictions |
| `*.csv` | Copied CSVs for the download buttons |

The frontend loads them via `fetch()` — so you must serve this folder over
HTTP, not open the HTML files with `file://`.

From `frontend/`:

```bash
python -m http.server 8000
# then open http://localhost:8000/index.html
```
