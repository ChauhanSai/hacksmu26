"""Stage 3: Statistical analysis — PMI, transitions, regional variation, name detection, herds."""

import math
import numpy as np
import pandas as pd
from collections import Counter, defaultdict
from scipy.stats import entropy, chi2_contingency


# ── Symbol sequences ──────────────────────────────────────────────────────────

def build_sequences(labels: np.ndarray, metadata: pd.DataFrame):
    """Group call symbols into per-session sequences."""
    sequences = defaultdict(list)
    for i, row in metadata.iterrows():
        session = row.get('session_id', row['filename'].rsplit('_', 1)[0])
        sequences[session].append(int(labels[i]))
    return list(sequences.values())


# ── PMI ───────────────────────────────────────────────────────────────────────

def compute_pmi_matrix(labels: np.ndarray, contexts, n_symbols: int):
    """PMI between every symbol and every behavioral context.

    Returns:
        pmi_matrix: np.ndarray (n_symbols, n_contexts)
        context_names: list of str
    """
    context_names = sorted(set(contexts))
    ctx_idx = {c: i for i, c in enumerate(context_names)}
    n_ctx = len(context_names)
    total = len(labels)

    joint = np.zeros((n_symbols, n_ctx))
    for sym, ctx in zip(labels, contexts):
        joint[sym][ctx_idx[ctx]] += 1

    sym_counts = joint.sum(axis=1)
    ctx_counts = joint.sum(axis=0)

    pmi = np.zeros((n_symbols, n_ctx))
    for i in range(n_symbols):
        for j in range(n_ctx):
            if joint[i][j] == 0:
                continue
            p_joint = joint[i][j] / total
            p_sym   = sym_counts[i] / total
            p_ctx   = ctx_counts[j] / total
            pmi[i][j] = math.log2(p_joint / (p_sym * p_ctx))

    return pmi, context_names


# ── Transition matrix ─────────────────────────────────────────────────────────

def build_transition_matrix(sequences: list, n_symbols: int):
    """Row-normalized symbol-to-symbol transition probability matrix."""
    trans = np.zeros((n_symbols, n_symbols))
    for seq in sequences:
        for a, b in zip(seq, seq[1:]):
            trans[a][b] += 1
    row_sums = trans.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    return trans / row_sums


def row_entropies(transition_matrix: np.ndarray) -> np.ndarray:
    """Low entropy = strong sequential constraint (proto-grammar signal)."""
    return np.array([entropy(row) for row in transition_matrix])


# ── Regional variation ────────────────────────────────────────────────────────

def analyze_regional_variation(labels: np.ndarray, metadata: pd.DataFrame, n_symbols: int):
    """Chi-squared test per symbol across regions: universal vs. learned."""
    if 'country' not in metadata.columns:
        print("No country column — skipping regional analysis")
        return None

    regions = metadata['country'].unique()
    results = []
    for s in range(n_symbols):
        contingency = np.array([
            [np.sum(labels[metadata['country'] == r] == s),
             np.sum(labels[metadata['country'] == r] != s)]
            for r in regions
        ])
        contingency = contingency + 1  # Laplace smoothing
        chi2, p_val, _, _ = chi2_contingency(contingency)
        results.append({
            'symbol': s,
            'chi2': chi2,
            'p_value': p_val,
            'type': 'UNIVERSAL' if p_val > 0.05 else 'REGIONAL',
        })
    return pd.DataFrame(results)


# ── Name detection ────────────────────────────────────────────────────────────

def detect_name_candidates(labels: np.ndarray, metadata: pd.DataFrame, n_symbols: int,
                            specificity_threshold: float = 0.75):
    """Find symbols a caller directs >75% at one specific receiver (name candidates)."""
    if 'receiver_id' not in metadata.columns or 'elephant_id' not in metadata.columns:
        print("No individual ID columns — skipping name detection")
        return None

    candidates = []
    for caller in metadata['elephant_id'].unique():
        caller_mask = metadata['elephant_id'] == caller
        caller_labels = labels[caller_mask]
        caller_meta = metadata[caller_mask]

        for symbol in range(n_symbols):
            sym_mask = caller_labels == symbol
            if sym_mask.sum() < 5:
                continue
            receivers = caller_meta[sym_mask]['receiver_id'].dropna()
            if len(receivers) == 0:
                continue
            top_rx = receivers.value_counts()
            fraction = top_rx.iloc[0] / len(receivers)
            if fraction > specificity_threshold:
                candidates.append({
                    'caller': caller,
                    'symbol': symbol,
                    'directed_at': top_rx.index[0],
                    'specificity': fraction,
                    'n_occurrences': int(sym_mask.sum()),
                })
    return pd.DataFrame(candidates)


# ── Herd inference ────────────────────────────────────────────────────────────

def infer_herds(metadata: pd.DataFrame, min_co_occurrences: int = 3) -> dict:
    """Louvain community detection on session co-occurrence graph."""
    try:
        import networkx as nx
        from networkx.algorithms.community import louvain_communities
    except ImportError:
        print("networkx not installed — skipping herd inference")
        return {}

    if 'elephant_id' not in metadata.columns or 'session_id' not in metadata.columns:
        print("Need elephant_id and session_id — skipping herd inference")
        return {}

    co_occ = defaultdict(int)
    for session in metadata['session_id'].unique():
        elephants = metadata[metadata['session_id'] == session]['elephant_id'].unique()
        for i in range(len(elephants)):
            for j in range(i + 1, len(elephants)):
                co_occ[tuple(sorted([elephants[i], elephants[j]]))] += 1

    G = nx.Graph()
    for (a, b), w in co_occ.items():
        if w >= min_co_occurrences:
            G.add_edge(a, b, weight=w)

    communities = louvain_communities(G, resolution=1.0)
    return {member: f"herd_{hid}" for hid, members in enumerate(communities) for member in members}
