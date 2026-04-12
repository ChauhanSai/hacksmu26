"""
Interactive cluster visualization for elephant call interpretations.

Produces a self-contained HTML file with:
  - UMAP 2D scatter of all calls (hover = full interpretation card)
  - Cluster boundary convex hulls
  - Background density heatmap
  - PMI symbol↔context heatmap
  - Context distribution bar chart
  - Valence/arousal breakdown

Usage:
    python visualize.py --csv sample_data/features.csv
    python visualize.py --csv sample_data/features.csv --output viz.html
"""

import argparse
import os
import warnings
import numpy as np
import pandas as pd
from scipy.spatial import ConvexHull

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

warnings.filterwarnings('ignore')

FEATURE_COLS = [
    'mean_f0', 'std_f0', 'f0_range', 'f0_slope',
    'mean_f1', 'mean_f2', 'mean_f3',
    'duration', 'attack_time', 'temporal_centroid',
    'rms_energy', 'mean_hnr', 'spectral_flatness',
    'spectral_centroid', 'spectral_bandwidth', 'spectral_rolloff',
    'mfcc_1', 'mfcc_2', 'mfcc_3', 'mfcc_4',
]

# Colorblind-friendly palette (15 contexts max)
PALETTE = px.colors.qualitative.Dark24


# ── Dimensionality reduction ──────────────────────────────────────────────────

def embed_2d(feature_matrix: np.ndarray) -> np.ndarray:
    """UMAP to 2D; falls back to PCA if umap-learn not installed."""
    try:
        import umap
        reducer = umap.UMAP(n_components=2, n_neighbors=15, min_dist=0.1,
                            metric='euclidean', random_state=42)
        return reducer.fit_transform(feature_matrix)
    except ImportError:
        print("umap-learn not found — using PCA instead (pip install umap-learn for better results)")
        from sklearn.decomposition import PCA
        return PCA(n_components=2, random_state=42).fit_transform(feature_matrix)


# ── Cluster pipeline (lightweight, inline) ───────────────────────────────────

def fit_pipeline(df: pd.DataFrame):
    from sklearn.preprocessing import StandardScaler
    from sklearn.mixture import GaussianMixture

    feature_names = [c for c in FEATURE_COLS if c in df.columns]
    X = df[feature_names].values.astype(float)

    scaler = StandardScaler()
    X_sc = scaler.fit_transform(X)

    # BIC-optimal GMM (cap at 20 for speed during viz)
    bics = []
    for k in range(5, 21):
        g = GaussianMixture(n_components=k, covariance_type='full', random_state=42)
        g.fit(X_sc)
        bics.append((k, g.bic(X_sc)))
    k_opt = min(bics, key=lambda x: x[1])[0]

    gmm = GaussianMixture(n_components=k_opt, covariance_type='full', random_state=42)
    gmm.fit(X_sc)

    return X, X_sc, feature_names, scaler, gmm, k_opt


# ── Convex hull boundaries ────────────────────────────────────────────────────

def hull_traces(coords_2d: np.ndarray, labels: np.ndarray, context_per_cluster: list,
                colors: list) -> list:
    """One filled convex-hull trace per cluster."""
    traces = []
    for cluster_id in np.unique(labels):
        pts = coords_2d[labels == cluster_id]
        if len(pts) < 4:
            continue
        try:
            hull = ConvexHull(pts)
            verts = pts[hull.vertices]
            verts = np.vstack([verts, verts[0]])  # close polygon
            color = colors[cluster_id % len(colors)]
            # rgba fill
            rgb = px.colors.hex_to_rgb(color) if color.startswith('#') else _named_to_rgb(color)
            fill_color = f"rgba({rgb[0]},{rgb[1]},{rgb[2]},0.10)"
            line_color = f"rgba({rgb[0]},{rgb[1]},{rgb[2]},0.55)"
            ctx_label = context_per_cluster[cluster_id] if cluster_id < len(context_per_cluster) else f"Cluster {cluster_id}"
            traces.append(go.Scatter(
                x=verts[:, 0], y=verts[:, 1],
                mode='lines',
                fill='toself',
                fillcolor=fill_color,
                line=dict(color=line_color, width=1.5, dash='dot'),
                name=f"C{cluster_id}: {ctx_label}",
                legendgroup=f"hull_{cluster_id}",
                showlegend=False,
                hoverinfo='skip',
            ))
        except Exception:
            pass
    return traces


def _named_to_rgb(color_str: str):
    """Extract rgb tuple from plotly 'rgb(r,g,b)' or return grey."""
    if color_str.startswith('rgb'):
        parts = color_str.replace('rgb(', '').replace(')', '').split(',')
        return tuple(int(p.strip()) for p in parts)
    return (128, 128, 128)


# ── PMI matrix ───────────────────────────────────────────────────────────────

def compute_pmi(labels: np.ndarray, contexts, n_symbols: int):
    import math
    ctx_names = sorted(set(contexts))
    ctx_idx   = {c: i for i, c in enumerate(ctx_names)}
    total     = len(labels)
    joint     = np.zeros((n_symbols, len(ctx_names)))
    for s, c in zip(labels, contexts):
        joint[s][ctx_idx[c]] += 1
    sym_c = joint.sum(axis=1)
    ctx_c = joint.sum(axis=0)
    pmi   = np.zeros_like(joint)
    for i in range(n_symbols):
        for j in range(len(ctx_names)):
            if joint[i][j] == 0:
                continue
            pmi[i][j] = math.log2((joint[i][j] / total) / ((sym_c[i] / total) * (ctx_c[j] / total)))
    return pmi, ctx_names


# ── Main visualization ────────────────────────────────────────────────────────

def build_viz(csv_path: str, output_path: str = 'output/visualization.html'):
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

    print("Loading data...")
    df = pd.read_csv(csv_path)

    # ── Fit pipeline ─────────────────────────────────────────────────────────
    print("Fitting GMM clusters...")
    X, X_sc, feature_names, scaler, gmm, k_opt = fit_pipeline(df)
    labels     = gmm.predict(X_sc)
    probs      = gmm.predict_proba(X_sc)
    confidence = probs.max(axis=1)

    print(f"Embedding {len(X)} calls to 2D (UMAP/PCA)...")
    coords = embed_2d(X_sc)

    df = df.copy()
    df['cluster']    = labels
    df['conf']       = confidence
    df['umap_x']     = coords[:, 0]
    df['umap_y']     = coords[:, 1]

    # ── Dominant context per cluster (for labels) ─────────────────────────────
    ctx_per_cluster = []
    for c in range(k_opt):
        mask = labels == c
        if mask.sum() == 0:
            ctx_per_cluster.append(f"C{c}")
            continue
        ctx_per_cluster.append(df[mask]['context'].value_counts().index[0])

    df['cluster_label'] = [f"C{c}: {ctx_per_cluster[c]}" for c in labels]

    # ── Colors ────────────────────────────────────────────────────────────────
    colors = PALETTE[:k_opt]

    # ── Hover text ────────────────────────────────────────────────────────────
    def _hover(row):
        ctx_probs_str = ""
        for feat in ['mean_f0', 'duration', 'rms_energy', 'mean_hnr']:
            if feat in row:
                ctx_probs_str += f"  {feat}: {row[feat]:.3f}<br>"
        return (
            f"<b>File:</b> {row.get('filename', 'N/A')}<br>"
            f"<b>Cluster:</b> {row['cluster']} ({row['conf']:.1%} confidence)<br>"
            f"<b>Context:</b> {row.get('context','?')}<br>"
            f"<b>Age/Sex:</b> {row.get('age_sex','?')}<br>"
            f"<b>Sound type:</b> {row.get('sound_type','?')}<br>"
            f"<b>Comm mode:</b> {row.get('comm_mode','?')}<br>"
            f"<b>Body part:</b> {row.get('body_part','?')}<br>"
            f"<b>Country:</b> {row.get('country','?')}<br>"
            f"─────────────────<br>"
            f"<b>Acoustic features:</b><br>{ctx_probs_str}"
            f"─────────────────<br>"
            f"<b>Session:</b> {row.get('session_id','?')}"
        )

    df['hover'] = df.apply(_hover, axis=1)

    # ── Build figure ──────────────────────────────────────────────────────────
    fig = make_subplots(
        rows=2, cols=2,
        specs=[[{"colspan": 2, "type": "xy"}, None],
               [{"type": "xy"},               {"type": "xy"}]],
        subplot_titles=(
            "Elephant Call Clusters — 2D Acoustic Space (UMAP)",
            "PMI: Symbol ↔ Behavioral Context",
            "Context Distribution",
        ),
        row_heights=[0.60, 0.40],
        vertical_spacing=0.10,
        horizontal_spacing=0.06,
    )

    # ── 1. Density heatmap background ─────────────────────────────────────────
    fig.add_trace(go.Histogram2dContour(
        x=coords[:, 0], y=coords[:, 1],
        colorscale='Blues',
        reversescale=False,
        showscale=False,
        opacity=0.35,
        contours=dict(showlines=False),
        ncontours=20,
        hoverinfo='skip',
        name='Density',
        showlegend=False,
    ), row=1, col=1)

    # ── 2. Convex hull boundaries ─────────────────────────────────────────────
    for hull_trace in hull_traces(coords, labels, ctx_per_cluster, colors):
        fig.add_trace(hull_trace, row=1, col=1)

    # ── 3. Scatter points per cluster ─────────────────────────────────────────
    for cluster_id in sorted(df['cluster'].unique()):
        sub = df[df['cluster'] == cluster_id]
        color = colors[cluster_id % len(colors)]
        fig.add_trace(go.Scatter(
            x=sub['umap_x'],
            y=sub['umap_y'],
            mode='markers',
            marker=dict(
                color=color,
                size=7,
                opacity=0.80,
                line=dict(width=0.5, color='white'),
                symbol='circle',
            ),
            name=f"C{cluster_id}: {ctx_per_cluster[cluster_id]}",
            text=sub['hover'],
            hovertemplate="%{text}<extra></extra>",
            legendgroup=f"cluster_{cluster_id}",
        ), row=1, col=1)

    # ── 4. Cluster centroid labels ────────────────────────────────────────────
    for cluster_id in range(k_opt):
        sub = df[df['cluster'] == cluster_id]
        if len(sub) == 0:
            continue
        cx, cy = sub['umap_x'].mean(), sub['umap_y'].mean()
        fig.add_annotation(
            x=cx, y=cy,
            text=f"<b>C{cluster_id}</b>",
            showarrow=False,
            font=dict(size=9, color='black'),
            bgcolor='rgba(255,255,255,0.6)',
            bordercolor='rgba(0,0,0,0.3)',
            borderwidth=1,
            borderpad=2,
            row=1, col=1,
        )

    # ── 5. PMI heatmap ────────────────────────────────────────────────────────
    pmi_matrix, ctx_names = compute_pmi(labels, df['context'].values, k_opt)
    fig.add_trace(go.Heatmap(
        z=pmi_matrix,
        x=ctx_names,
        y=[f"C{i}" for i in range(k_opt)],
        colorscale='RdYlGn',
        zmid=0,
        colorbar=dict(title='PMI', x=0.47, len=0.38, y=0.18),
        hovertemplate="Symbol: %{y}<br>Context: %{x}<br>PMI: %{z:.2f}<extra></extra>",
        name='PMI',
    ), row=2, col=1)

    # ── 6. Context bar chart ──────────────────────────────────────────────────
    ctx_counts = df['context'].value_counts()
    ctx_colors = [PALETTE[i % len(PALETTE)] for i in range(len(ctx_counts))]
    fig.add_trace(go.Bar(
        x=ctx_counts.index.tolist(),
        y=ctx_counts.values.tolist(),
        marker_color=ctx_colors,
        hovertemplate="%{x}: %{y} calls<extra></extra>",
        name='Context counts',
        showlegend=False,
    ), row=2, col=2)

    # ── Layout ────────────────────────────────────────────────────────────────
    fig.update_layout(
        title=dict(
            text="<b>Elephant Communication Decoder</b> — Acoustic Cluster Analysis",
            font=dict(size=18),
            x=0.5,
        ),
        height=1000,
        template='plotly_white',
        legend=dict(
            title="Clusters",
            x=1.01, y=1,
            font=dict(size=10),
            bordercolor='lightgrey',
            borderwidth=1,
        ),
        hoverlabel=dict(
            bgcolor='rgba(30,30,30,0.88)',
            font_size=12,
            font_color='white',
            bordercolor='rgba(255,255,255,0.3)',
        ),
        margin=dict(l=60, r=200, t=80, b=60),
    )

    fig.update_xaxes(title_text="UMAP Dimension 1", row=1, col=1, showgrid=False)
    fig.update_yaxes(title_text="UMAP Dimension 2", row=1, col=1, showgrid=False)
    fig.update_xaxes(title_text="Behavioral Context", row=2, col=2,
                     tickangle=-35, tickfont=dict(size=9))
    fig.update_yaxes(title_text="Call Count", row=2, col=2)
    fig.update_xaxes(tickfont=dict(size=8), tickangle=-35, row=2, col=1)
    fig.update_yaxes(title_text="Cluster Symbol", row=2, col=1, tickfont=dict(size=8))

    # ── Export ────────────────────────────────────────────────────────────────
    fig.write_html(
        output_path,
        include_plotlyjs='cdn',
        config={
            'displayModeBar': True,
            'scrollZoom': True,
            'toImageButtonOptions': {'format': 'png', 'scale': 2},
        },
    )
    print(f"Visualization saved → {output_path}")
    return fig


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv',    required=True, help='Path to features CSV')
    parser.add_argument('--output', default='output/visualization.html')
    args = parser.parse_args()

    build_viz(args.csv, args.output)
