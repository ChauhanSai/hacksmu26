"""
Advanced inference — caller identification, voice fingerprinting,
enhanced context prediction, and call similarity search.

Key capabilities:
  1. Caller classifier:     "Which elephant made this call?"
  2. Voice profiles:         Per-elephant acoustic fingerprint
  3. Identifiability scores: How distinctive is each elephant's voice?
  4. Enhanced context model: Combines acoustics + metadata features
  5. Caller-context affinity: Does elephant X prefer context Y?
  6. Nearest-call search:    Find k most similar calls to a query
  7. Full call inference:    Combined "who + what + why" report
"""

import numpy as np
import pandas as pd
from collections import Counter
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.metrics import classification_report
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import OneHotEncoder
from scipy.stats import chi2_contingency
from scipy.spatial.distance import cdist


# ═══════════════════════════════════════════════════════════════════════════════
# 1. CALLER IDENTIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

def train_caller_classifier(X_scaled: np.ndarray, metadata: pd.DataFrame,
                             min_calls_per_caller: int = 3):
    """
    Train a classifier to predict which elephant produced a given call.

    Individual elephants have distinct 'voice fingerprints' due to body size,
    vocal tract morphology, and learned patterns. F0, formants, and HNR are
    especially individual-specific.

    Returns:
        caller_clf:  trained classifier (None if not enough data)
        train_mask:  boolean mask for rows with qualifying callers
        cv_score:    mean cross-validation accuracy
        known_callers: list of elephant_ids the model can predict
    """
    if 'elephant_id' not in metadata.columns:
        print("  [caller] No elephant_id column — skipping caller classifier")
        return None, None, None, []

    caller_counts = metadata['elephant_id'].value_counts()
    known_callers = caller_counts[caller_counts >= min_calls_per_caller].index.tolist()

    if len(known_callers) < 2:
        print(f"  [caller] Only {len(known_callers)} callers with ≥{min_calls_per_caller} "
              f"calls — skipping caller classifier")
        return None, None, None, []

    mask = metadata['elephant_id'].isin(known_callers).values
    X_sub = X_scaled[mask]
    y_sub = metadata.loc[mask, 'elephant_id'].values

    clf = RandomForestClassifier(
        n_estimators=300,
        max_depth=None,
        min_samples_leaf=2,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1,
    )
    clf.fit(X_sub, y_sub)

    # Stratified CV (only if each class has ≥2 samples)
    try:
        n_splits = min(5, caller_counts[known_callers].min())
        if n_splits >= 2:
            cv = cross_val_score(clf, X_sub, y_sub,
                                  cv=StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42))
            cv_score = cv.mean()
            print(f"  [caller] Classifier trained on {len(known_callers)} elephants, "
                  f"{len(X_sub)} calls — CV accuracy: {cv_score:.3f}")
        else:
            cv_score = None
            print(f"  [caller] Classifier trained on {len(known_callers)} elephants "
                  f"(CV skipped — too few samples per class)")
    except Exception as e:
        cv_score = None
        print(f"  [caller] CV failed: {e}")

    return clf, mask, cv_score, known_callers


def predict_caller(caller_clf, X_scaled_row: np.ndarray, top_k: int = 3):
    """Return top-k most likely callers with probabilities."""
    if caller_clf is None:
        return []
    probs = caller_clf.predict_proba(X_scaled_row.reshape(1, -1))[0]
    idxs = np.argsort(probs)[::-1][:top_k]
    return [(caller_clf.classes_[i], float(probs[i])) for i in idxs]


# ═══════════════════════════════════════════════════════════════════════════════
# 2. VOICE FINGERPRINTS
# ═══════════════════════════════════════════════════════════════════════════════

def build_voice_profiles(feature_matrix: np.ndarray, metadata: pd.DataFrame,
                          feature_names: list) -> pd.DataFrame:
    """
    Build per-elephant 'voice fingerprint' — mean and std of each feature.

    Returns DataFrame indexed by elephant_id, columns are {feature}_mean, {feature}_std.
    This is the acoustic signature you can compare new calls against.
    """
    if 'elephant_id' not in metadata.columns:
        return pd.DataFrame()

    rows = []
    for eid in metadata['elephant_id'].dropna().unique():
        mask = metadata['elephant_id'] == eid
        n = mask.sum()
        if n < 2:
            continue
        row = {'elephant_id': eid, 'n_calls': int(n)}
        for i, feat in enumerate(feature_names):
            vals = feature_matrix[mask.values, i]
            row[f"{feat}_mean"] = float(vals.mean())
            row[f"{feat}_std"]  = float(vals.std())
        rows.append(row)

    return pd.DataFrame(rows).set_index('elephant_id')


def caller_identifiability(feature_matrix: np.ndarray, metadata: pd.DataFrame) -> pd.DataFrame:
    """
    Score how acoustically distinctive each elephant is.

    A high score means the elephant's calls cluster tightly and differ from others —
    that caller has a recognizable 'voice'. Low = blends in with the population.

    Score = mean_between_distance / (mean_within_distance + epsilon)
    """
    if 'elephant_id' not in metadata.columns:
        return pd.DataFrame()

    callers = metadata['elephant_id'].dropna().unique()
    results = []

    for eid in callers:
        mask = (metadata['elephant_id'] == eid).values
        n = mask.sum()
        if n < 2:
            continue

        own = feature_matrix[mask]
        other = feature_matrix[~mask]

        within  = cdist(own, own).mean()
        between = cdist(own, other).mean() if len(other) > 0 else 0
        score   = between / (within + 1e-6)

        results.append({
            'elephant_id': eid,
            'n_calls': int(n),
            'within_distance':  float(within),
            'between_distance': float(between),
            'identifiability':  float(score),
        })

    df = pd.DataFrame(results)
    if len(df) > 0:
        df = df.sort_values('identifiability', ascending=False).reset_index(drop=True)
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# 3. ENHANCED CONTEXT CLASSIFIER (acoustics + metadata)
# ═══════════════════════════════════════════════════════════════════════════════

def build_enhanced_features(X_scaled: np.ndarray, metadata: pd.DataFrame,
                             meta_cols: list = None):
    """
    Augment acoustic features with one-hot metadata (age_sex, body_part,
    comm_mode, sound_type). This gives the context classifier extra signal
    beyond pure acoustics.

    Returns: (X_enhanced, encoder, meta_feature_names)
    """
    if meta_cols is None:
        meta_cols = ['age_sex', 'body_part', 'comm_mode', 'sound_type']

    available = [c for c in meta_cols if c in metadata.columns]
    if not available:
        return X_scaled, None, []

    encoder = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
    meta_vals = metadata[available].fillna('unknown').values
    meta_encoded = encoder.fit_transform(meta_vals)

    meta_feature_names = []
    for col, cats in zip(available, encoder.categories_):
        meta_feature_names.extend([f"{col}={c}" for c in cats])

    X_enhanced = np.hstack([X_scaled, meta_encoded])
    return X_enhanced, encoder, meta_feature_names


def train_enhanced_context(X_enhanced: np.ndarray, metadata: pd.DataFrame):
    """Gradient Boosting on acoustics + metadata features for context."""
    y = metadata['context'].values
    clf = GradientBoostingClassifier(n_estimators=200, max_depth=4, random_state=42)
    clf.fit(X_enhanced, y)

    try:
        cv = cross_val_score(clf, X_enhanced, y, cv=5)
        print(f"  [enhanced context] CV accuracy: {cv.mean():.3f} ± {cv.std():.3f}")
    except Exception:
        pass

    return clf


# ═══════════════════════════════════════════════════════════════════════════════
# 4. CALLER-CONTEXT AFFINITY (who prefers which contexts?)
# ═══════════════════════════════════════════════════════════════════════════════

def caller_context_affinity(metadata: pd.DataFrame, top_n_contexts: int = 3) -> pd.DataFrame:
    """
    For each elephant, rank which behavioral contexts they vocalize in most.
    Also runs chi-squared test: does this caller deviate from the population distribution?
    """
    if 'elephant_id' not in metadata.columns or 'context' not in metadata.columns:
        return pd.DataFrame()

    pop_dist = metadata['context'].value_counts(normalize=True)
    contexts_all = pop_dist.index.tolist()

    rows = []
    for eid in metadata['elephant_id'].dropna().unique():
        sub = metadata[metadata['elephant_id'] == eid]
        if len(sub) < 5:
            continue

        caller_counts = sub['context'].value_counts()
        caller_dist = caller_counts / caller_counts.sum()

        # Chi-squared vs. population
        observed = np.array([caller_counts.get(c, 0) for c in contexts_all])
        expected = np.array([pop_dist[c] * len(sub) for c in contexts_all])
        expected = np.where(expected < 1, 1, expected)
        try:
            chi2 = float(np.sum((observed - expected) ** 2 / expected))
        except Exception:
            chi2 = 0.0

        top_ctxs = caller_dist.head(top_n_contexts)
        rows.append({
            'elephant_id':  eid,
            'n_calls':      int(len(sub)),
            'top_contexts': ', '.join([f"{c} ({p:.0%})" for c, p in top_ctxs.items()]),
            'deviation_chi2': round(chi2, 2),
            'specialist':     chi2 > 20,  # high = specialized caller
        })

    df = pd.DataFrame(rows)
    if len(df) > 0:
        df = df.sort_values('deviation_chi2', ascending=False).reset_index(drop=True)
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# 5. NEAREST-CALL SEARCH (acoustic similarity)
# ═══════════════════════════════════════════════════════════════════════════════

class CallSimilaritySearch:
    """k-NN acoustic similarity search. Given a call, find the most similar ones."""

    def __init__(self, X_scaled: np.ndarray, metadata: pd.DataFrame, k: int = 5):
        self.X = X_scaled
        self.metadata = metadata.reset_index(drop=True)
        self.k = k
        self.nn = NearestNeighbors(n_neighbors=k + 1, metric='euclidean')
        self.nn.fit(X_scaled)

    def query(self, call_idx: int) -> pd.DataFrame:
        """Return the k nearest acoustic neighbors of a call (excluding itself)."""
        dists, idxs = self.nn.kneighbors(self.X[call_idx].reshape(1, -1))
        # Drop the query itself (idx 0)
        dists, idxs = dists[0][1:], idxs[0][1:]
        return pd.DataFrame({
            'neighbor_idx': idxs,
            'distance':     dists,
            'filename':     self.metadata.iloc[idxs]['filename'].values,
            'context':      self.metadata.iloc[idxs]['context'].values,
            'elephant_id':  self.metadata.iloc[idxs].get('elephant_id', pd.Series(['?'] * len(idxs))).values,
        })


# ═══════════════════════════════════════════════════════════════════════════════
# 6. FULL CALL INFERENCE (who + what + why)
# ═══════════════════════════════════════════════════════════════════════════════

def full_call_inference(call_idx: int, X_scaled: np.ndarray, metadata: pd.DataFrame,
                         caller_clf, enhanced_context_clf, X_enhanced: np.ndarray,
                         similarity_search: CallSimilaritySearch,
                         voice_profiles: pd.DataFrame) -> dict:
    """
    Produce a comprehensive 'who + what + why' report for a single call.
    """
    row = metadata.iloc[call_idx]
    result = {
        'call_idx':     call_idx,
        'filename':     row.get('filename', f'call_{call_idx}'),
        'true_caller':  row.get('elephant_id', '?'),
        'true_context': row.get('context', '?'),
    }

    # WHO — caller prediction
    if caller_clf is not None:
        top_callers = predict_caller(caller_clf, X_scaled[call_idx], top_k=3)
        result['predicted_caller_top3'] = top_callers
        result['predicted_caller'] = top_callers[0][0] if top_callers else None
        result['caller_confidence'] = top_callers[0][1] if top_callers else 0.0

    # WHAT — enhanced context prediction
    if enhanced_context_clf is not None:
        probs = enhanced_context_clf.predict_proba(X_enhanced[call_idx].reshape(1, -1))[0]
        idxs = np.argsort(probs)[::-1][:3]
        result['predicted_context_top3'] = [
            (enhanced_context_clf.classes_[i], float(probs[i])) for i in idxs
        ]
        result['predicted_context']   = enhanced_context_clf.classes_[idxs[0]]
        result['context_confidence']  = float(probs[idxs[0]])

    # WHY — similar calls (nearest neighbors in acoustic space)
    neighbors = similarity_search.query(call_idx)
    result['similar_calls'] = neighbors.to_dict('records')

    # Voice profile match (is this call consistent with its predicted caller's fingerprint?)
    if (caller_clf is not None and voice_profiles is not None
            and not voice_profiles.empty and result.get('predicted_caller')):
        predicted = result['predicted_caller']
        if predicted in voice_profiles.index:
            profile = voice_profiles.loc[predicted]
            mean_cols = [c for c in profile.index if c.endswith('_mean')]
            if mean_cols:
                # Z-score distance from the caller's feature means
                devs = []
                for c in mean_cols:
                    feat = c[:-5]  # strip '_mean'
                    std_col = f"{feat}_std"
                    if std_col in profile.index and profile[std_col] > 0:
                        feat_idx = mean_cols.index(c)
                        actual = X_scaled[call_idx, feat_idx] if feat_idx < X_scaled.shape[1] else 0
                        z = abs(actual - profile[c]) / (profile[std_col] + 1e-6)
                        devs.append(z)
                if devs:
                    result['voice_match_zscore'] = float(np.mean(devs))

    return result


def print_full_inference(report: dict):
    """Pretty-print a full-call inference report."""
    sep = '═' * 70
    print(f"\n{sep}")
    print(f"FULL CALL INFERENCE — {report['filename']}")
    print(sep)

    print(f"\n🎯 GROUND TRUTH")
    print(f"   Caller:  {report.get('true_caller', '?')}")
    print(f"   Context: {report.get('true_context', '?')}")

    if 'predicted_caller_top3' in report:
        print(f"\n🐘 WHO (predicted caller)")
        for i, (eid, p) in enumerate(report['predicted_caller_top3'], 1):
            marker = "✓" if eid == report.get('true_caller') else " "
            print(f"   {marker} {i}. {eid} — {p:.1%}")
        if 'voice_match_zscore' in report:
            print(f"   Voice fingerprint match: z={report['voice_match_zscore']:.2f} "
                  f"({'strong' if report['voice_match_zscore'] < 1.5 else 'weak'})")

    if 'predicted_context_top3' in report:
        print(f"\n💬 WHAT (predicted context)")
        for i, (ctx, p) in enumerate(report['predicted_context_top3'], 1):
            marker = "✓" if ctx == report.get('true_context') else " "
            print(f"   {marker} {i}. {ctx} — {p:.1%}")

    if 'similar_calls' in report and report['similar_calls']:
        print(f"\n🔗 WHY (most acoustically similar calls)")
        for i, nb in enumerate(report['similar_calls'][:3], 1):
            print(f"   {i}. {nb['filename']} (dist={nb['distance']:.2f}) — "
                  f"{nb['elephant_id']} / {nb['context']}")
    print(sep)
