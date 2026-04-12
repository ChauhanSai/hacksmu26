"""
Export all pipeline results as JSON files the frontend can consume.
Also copies the CSV outputs so they can be downloaded from the dashboard.
"""

import json
import os
import shutil
import numpy as np
import pandas as pd
from scipy.spatial import ConvexHull


PALETTE = ["#4caf50", "#7b1fa2", "#e53935", "#fdd835", "#ff9800", "#26a69a"]


def _pick_color(i: int) -> str:
    return PALETTE[i % len(PALETTE)]


def _np_safe(obj):
    """Recursively convert numpy types so json.dump works."""
    if isinstance(obj, dict):
        return {k: _np_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_np_safe(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    if isinstance(obj, (np.floating, np.float64, np.float32)):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return float(obj)
    if isinstance(obj, pd.Series):
        return _np_safe(obj.to_dict())
    if pd.isna(obj) if not isinstance(obj, (list, dict, np.ndarray)) else False:
        return None
    return obj


def _write_json(path: str, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(_np_safe(data), f, indent=2, default=str)


# ── Main export ──────────────────────────────────────────────────────────────

def export_all(
    target_dir: str,
    *,
    feature_matrix: np.ndarray,
    feature_names: list,
    metadata: pd.DataFrame,
    X_scaled: np.ndarray,
    coords_2d: np.ndarray,
    labels: np.ndarray,
    pmi_matrix: np.ndarray,
    context_names: list,
    transition_matrix: np.ndarray,
    k_opt: int,
    results_df: pd.DataFrame,
    voice_profiles: pd.DataFrame,
    identifiability_df: pd.DataFrame,
    affinity_df: pd.DataFrame,
    cv_scores: dict,
    caller_cv_score: float = None,
    known_callers: list = None,
    output_csv_dir: str = None,
):
    """Write all JSON files and CSV copies to target_dir."""
    os.makedirs(target_dir, exist_ok=True)

    # ── Dominant context per cluster ─────────────────────────────────────────
    ctx_per_cluster = []
    for c in range(k_opt):
        mask = labels == c
        if mask.sum() == 0:
            ctx_per_cluster.append(f"C{c}")
        else:
            ctx_per_cluster.append(metadata.loc[mask, 'context'].value_counts().index[0])

    # ── clusters.json ────────────────────────────────────────────────────────
    points = []
    for i in range(len(coords_2d)):
        row = metadata.iloc[i]
        points.append({
            'idx': int(i),
            'x': float(coords_2d[i, 0]),
            'y': float(coords_2d[i, 1]),
            'cluster': int(labels[i]),
            'filename': row.get('filename', f'call_{i}'),
            'context': row.get('context', '?'),
            'age_sex': row.get('age_sex', '?'),
            'elephant_id': row.get('elephant_id', '?'),
            'sound_type': row.get('sound_type', '?'),
            'comm_mode': row.get('comm_mode', '?'),
            'body_part': row.get('body_part', '?'),
            'country': row.get('country', '?'),
            'session_id': str(row.get('session_id', '?')),
            'mean_f0': float(feature_matrix[i, feature_names.index('mean_f0')]) if 'mean_f0' in feature_names else None,
            'duration': float(feature_matrix[i, feature_names.index('duration')]) if 'duration' in feature_names else None,
            'rms_energy': float(feature_matrix[i, feature_names.index('rms_energy')]) if 'rms_energy' in feature_names else None,
        })

    # Convex hulls per cluster
    cluster_meta = []
    for c in range(k_opt):
        pts = coords_2d[labels == c]
        centroid = pts.mean(axis=0) if len(pts) > 0 else [0, 0]
        hull_pts = []
        if len(pts) >= 4:
            try:
                hull = ConvexHull(pts)
                hull_pts = [[float(pts[v, 0]), float(pts[v, 1])] for v in hull.vertices]
                hull_pts.append(hull_pts[0])  # close polygon
            except Exception:
                pass
        cluster_meta.append({
            'id': int(c),
            'label': f"C{c}: {ctx_per_cluster[c]}",
            'top_context': ctx_per_cluster[c],
            'color': _pick_color(c),
            'count': int(np.sum(labels == c)),
            'centroid': [float(centroid[0]), float(centroid[1])],
            'hull': hull_pts,
        })

    _write_json(os.path.join(target_dir, 'clusters.json'), {
        'points': points,
        'clusters': cluster_meta,
        'k_opt': int(k_opt),
    })

    # ── pmi_matrix.json ──────────────────────────────────────────────────────
    _write_json(os.path.join(target_dir, 'pmi_matrix.json'), {
        'symbols': [f"C{i}" for i in range(k_opt)],
        'contexts': list(context_names),
        'values': pmi_matrix.tolist(),
    })

    # ── transition_matrix.json ───────────────────────────────────────────────
    _write_json(os.path.join(target_dir, 'transition_matrix.json'), {
        'symbols': [f"C{i}" for i in range(k_opt)],
        'values': transition_matrix.tolist(),
    })

    # ── context_distribution.json ────────────────────────────────────────────
    ctx_counts = metadata['context'].value_counts()
    _write_json(os.path.join(target_dir, 'context_distribution.json'), {
        'contexts': ctx_counts.index.tolist(),
        'counts': [int(v) for v in ctx_counts.values],
    })

    # ── vowel_space.json (F1/F2) ─────────────────────────────────────────────
    if 'mean_f1' in feature_names and 'mean_f2' in feature_names:
        f1 = feature_matrix[:, feature_names.index('mean_f1')]
        f2 = feature_matrix[:, feature_names.index('mean_f2')]
        valid = ~(np.isnan(f1) | np.isnan(f2))
        _write_json(os.path.join(target_dir, 'vowel_space.json'), {
            'f1': f1[valid].tolist(),
            'f2': f2[valid].tolist(),
            'clusters': labels[valid].tolist(),
            'contexts': metadata.loc[valid, 'context'].tolist(),
        })

    # ── caller_identifiability.json ──────────────────────────────────────────
    if identifiability_df is not None and not identifiability_df.empty:
        top = identifiability_df.head(15)
        _write_json(os.path.join(target_dir, 'caller_identifiability.json'), {
            'callers': top['elephant_id'].tolist(),
            'scores': [float(v) for v in top['identifiability'].values],
            'n_calls': [int(v) for v in top['n_calls'].values],
        })

    # ── voice_profiles.json ──────────────────────────────────────────────────
    if voice_profiles is not None and not voice_profiles.empty:
        key_features = ['mean_f0', 'mean_f1', 'mean_f2', 'mean_hnr', 'duration', 'rms_energy']
        rows = []
        for eid, row in voice_profiles.iterrows():
            rows.append({
                'elephant_id': eid,
                'n_calls': int(row['n_calls']),
                **{f: float(row[f"{f}_mean"]) for f in key_features if f"{f}_mean" in row.index},
            })
        _write_json(os.path.join(target_dir, 'voice_profiles.json'), rows)

    # ── caller_affinity.json ─────────────────────────────────────────────────
    if affinity_df is not None and not affinity_df.empty:
        _write_json(os.path.join(target_dir, 'caller_affinity.json'),
                    affinity_df.head(15).to_dict('records'))

    # ── sample_interpretations.json (for WHO/WHAT/WHY cards) ─────────────────
    if results_df is not None and not results_df.empty:
        sample = results_df.head(8).to_dict('records')
        cleaned = []
        for r in sample:
            cleaned.append({
                'filename': r.get('filename'),
                'symbol': int(r.get('symbol', 0)),
                'top_context': r.get('top_context'),
                'context_confidence': float(r.get('context_confidence', 0)),
                'alt_context': r.get('alt_context'),
                'alt_confidence': float(r.get('alt_confidence', 0)),
                'valence': r.get('valence'),
                'arousal': r.get('arousal'),
                'caller_age_sex': r.get('caller_age_sex'),
                'interpretation': r.get('interpretation'),
                'confidence': r.get('confidence'),
                'alternative': r.get('alternative'),
            })
        _write_json(os.path.join(target_dir, 'sample_interpretations.json'), cleaned)

    # ── summary.json ─────────────────────────────────────────────────────────
    summary = {
        'n_calls':       int(len(metadata)),
        'n_clusters':    int(k_opt),
        'n_contexts':    int(metadata['context'].nunique()),
        'n_elephants':   int(metadata['elephant_id'].nunique()) if 'elephant_id' in metadata.columns else 0,
        'n_sessions':    int(metadata['session_id'].nunique()) if 'session_id' in metadata.columns else 0,
        'context_accuracy': float(cv_scores.get('context_cv_mean', 0) or 0),
        'caller_accuracy':  float(caller_cv_score) if caller_cv_score is not None else None,
        'known_callers':    len(known_callers) if known_callers else 0,
        'palette':          PALETTE,
    }
    _write_json(os.path.join(target_dir, 'summary.json'), summary)

    # ── Copy CSV files for download buttons ──────────────────────────────────
    if output_csv_dir and os.path.isdir(output_csv_dir):
        for name in os.listdir(output_csv_dir):
            if name.endswith('.csv'):
                try:
                    shutil.copy(os.path.join(output_csv_dir, name), os.path.join(target_dir, name))
                except Exception as e:
                    print(f"  [export] could not copy {name}: {e}")

    print(f"  [export] Frontend data written to {target_dir}/")
