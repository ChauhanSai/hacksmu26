"""Stage 2: Normalization and GMM clustering."""

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.mixture import GaussianMixture


def normalize(feature_matrix: np.ndarray, metadata: pd.DataFrame, feature_names: list):
    """StandardScale + age/sex-normalize F0 features within demographic groups."""
    F0_FEATURES = ['mean_f0', 'std_f0', 'f0_range', 'f0_slope']

    # Age/sex normalization before global scaling — prevents body-size clustering
    if 'age_sex' in metadata.columns:
        for group in metadata['age_sex'].unique():
            mask = metadata['age_sex'] == group
            for feat in F0_FEATURES:
                if feat not in feature_names:
                    continue
                col = feature_names.index(feat)
                vals = feature_matrix[mask, col]
                std = vals.std()
                if std > 0:
                    feature_matrix[mask, col] = (vals - vals.mean()) / std

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(feature_matrix)
    return X_scaled, scaler


def cluster_calls(X_scaled: np.ndarray, k_min: int = 5, k_max: int = 51):
    """Fit GMM with BIC-optimal k. Returns labels, probabilities, and fitted GMM."""
    bics = []
    for k in range(k_min, k_max):
        g = GaussianMixture(n_components=k, covariance_type='full', random_state=42)
        g.fit(X_scaled)
        bics.append((k, g.bic(X_scaled)))

    optimal_k = min(bics, key=lambda x: x[1])[0]
    print(f"Optimal call types (BIC): {optimal_k}")

    gmm = GaussianMixture(n_components=optimal_k, covariance_type='full', random_state=42)
    gmm.fit(X_scaled)

    labels = gmm.predict(X_scaled)
    probabilities = gmm.predict_proba(X_scaled)
    return labels, probabilities, gmm, optimal_k


def cluster_vowels(feature_matrix: np.ndarray, feature_names: list, n_vowel_types: int = 5):
    """Cluster calls in F1/F2 space to find 'elephant vowels'."""
    f1_idx = feature_names.index('mean_f1')
    f2_idx = feature_names.index('mean_f2')
    f1f2 = feature_matrix[:, [f1_idx, f2_idx]]
    clean_mask = ~np.isnan(f1f2).any(axis=1)

    vowel_gmm = GaussianMixture(n_components=n_vowel_types, random_state=42)
    vowel_labels = vowel_gmm.fit_predict(f1f2[clean_mask])
    return vowel_labels, vowel_gmm, clean_mask
