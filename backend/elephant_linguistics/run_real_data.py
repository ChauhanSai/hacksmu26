"""
Pipeline runner for REAL elephant ethogram data.

Reads data.csv + segmented WAV files, extracts acoustic features,
runs the full analysis pipeline (Stages 1-6), and exports JSON
for the frontend dashboard.

Usage:
    cd backend/elephant_linguistics
    python run_real_data.py
    python run_real_data.py --max-segments 200   # quick test run
"""

import argparse
import os
import sys
import numpy as np
import pandas as pd
import joblib
import warnings
warnings.filterwarnings('ignore')

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DATA_CSV = os.path.join(BASE_DIR, 'backend', 'elephant_ethogram', 'data.csv')
AUDIO_DIR = os.path.join(BASE_DIR, 'segmented-20260412T062525Z-3-001', 'segmented')
OUTPUT_DIR = os.path.join(BASE_DIR, 'backend', 'elephant_linguistics', 'output')
FRONTEND_DATA_DIR = os.path.join(BASE_DIR, 'frontend', 'data')

FEATURE_COLS = [
    'mean_f0', 'std_f0', 'f0_range', 'f0_slope',
    'mean_f1', 'mean_f2', 'mean_f3',
    'duration', 'attack_time', 'temporal_centroid',
    'rms_energy', 'mean_hnr', 'spectral_flatness',
    'spectral_centroid', 'spectral_bandwidth', 'spectral_rolloff',
    'mfcc_1', 'mfcc_2', 'mfcc_3', 'mfcc_4',
]

# ── Context label cleanup ────────────────────────────────────────────────────
CONTEXT_FIXES = {
    'ocial Play': 'Social Play',
    '& Mobbing': 'Attacking & Mobbing',
    'Movement, Space & Leadership': 'Movement Space & Leadership',
}


def clean_context(ctx):
    """Fix typos and remove garbage LLM-generated labels."""
    if not isinstance(ctx, str):
        return None
    ctx = ctx.strip()
    if ctx in CONTEXT_FIXES:
        return CONTEXT_FIXES[ctx]
    # Drop garbage rows (LLM outputs that leaked into the CSV)
    if len(ctx) > 60 or 'categorize' in ctx.lower() or 'observation' in ctx.lower():
        return None
    return ctx


# ── Build expanded dataset: one row per audio segment ────────────────────────

def build_segment_dataframe(data_csv, audio_dir, max_segments=None):
    """Map each segment WAV to its parent metadata row."""
    df = pd.read_csv(data_csv)
    print(f"Loaded {len(df)} metadata rows from {data_csv}")

    # Clean contexts
    df['context'] = df['context'].apply(clean_context)
    df = df.dropna(subset=['context']).reset_index(drop=True)
    print(f"After cleaning contexts: {len(df)} rows, {df['context'].nunique()} contexts")

    wavs = set(os.listdir(audio_dir))
    print(f"Found {len(wavs)} WAV files in {audio_dir}")

    rows = []
    for _, row in df.iterrows():
        fn = row['file_name']
        segs = sorted([w for w in wavs if w.startswith(fn + '_seg')])
        for seg in segs:
            # Derive metadata columns the pipeline expects
            age = str(row.get('age', ''))
            gender = str(row.get('gender', ''))
            if gender == 'nan':
                gender = ''
            age_sex = f"{age} {gender}".strip() if age or gender else 'unknown'

            rows.append({
                'filename': seg,
                'context': row['context'],
                'sound_type': row.get('name', 'unknown'),
                'age_sex': age_sex,
                'comm_mode': row.get('mode', 'unknown'),
                'description': row.get('description', ''),
                'url': row.get('url', ''),
                # Use file_name prefix as session_id (groups segments from same video)
                'session_id': fn,
                # Use call type name as elephant_id proxy (no real IDs in this dataset)
                'elephant_id': row.get('name', 'unknown'),
                'body_part': 'vocal',
                'country': 'Kenya',
            })

    seg_df = pd.DataFrame(rows)
    print(f"Expanded to {len(seg_df)} segments")

    if max_segments and len(seg_df) > max_segments:
        seg_df = seg_df.sample(n=max_segments, random_state=42).reset_index(drop=True)
        print(f"Sampled down to {max_segments} segments for speed")

    return seg_df


# ── Feature extraction ───────────────────────────────────────────────────────

def extract_features_from_segments(seg_df, audio_dir):
    """Extract 20 acoustic features from each segment WAV."""
    from features import extract_features
    import librosa

    all_features = []
    valid_indices = []
    total = len(seg_df)

    for idx, row in seg_df.iterrows():
        filepath = os.path.join(audio_dir, row['filename'])
        try:
            y, sr = librosa.load(filepath, sr=None)
            if len(y) < sr * 0.1:  # skip segments shorter than 100ms
                continue
            feats = extract_features(y, sr)
            all_features.append(feats)
            valid_indices.append(idx)
            if len(valid_indices) % 100 == 0:
                print(f"  Extracted {len(valid_indices)}/{total} ...")
        except Exception as e:
            print(f"  Skip {row['filename']}: {e}")

    feature_df = pd.DataFrame(all_features)
    feature_matrix = feature_df.values.astype(float)
    feature_names = list(feature_df.columns)
    metadata = seg_df.loc[valid_indices].reset_index(drop=True)

    # Replace NaN/inf in features
    feature_matrix = np.nan_to_num(feature_matrix, nan=0.0, posinf=0.0, neginf=0.0)

    print(f"  Feature extraction complete: {len(feature_matrix)} calls, {len(feature_names)} features")
    return feature_matrix, feature_names, metadata


# ── Main pipeline ────────────────────────────────────────────────────────────

def run(max_segments=None, no_plots=False):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ── Stage 0: Build segment dataset ──────────────────────────────────────
    print("\n" + "=" * 70)
    print("TUSK AND TIDY — Real Data Pipeline")
    print("=" * 70)

    seg_df = build_segment_dataframe(DATA_CSV, AUDIO_DIR, max_segments)

    # ── Stage 1: Feature extraction ─────────────────────────────────────────
    print("\nStage 1: Extracting acoustic features...")
    feature_matrix, feature_names, metadata = extract_features_from_segments(seg_df, AUDIO_DIR)

    # Save extracted features CSV for future fast reruns
    features_csv = os.path.join(OUTPUT_DIR, 'real_features.csv')
    feat_df = pd.DataFrame(feature_matrix, columns=feature_names)
    combined = pd.concat([metadata.reset_index(drop=True), feat_df], axis=1)
    combined.to_csv(features_csv, index=False)
    print(f"  Saved features -> {features_csv}")

    # ── Stage 2: Normalize + Cluster ────────────────────────────────────────
    print("\nStage 2: Normalizing and clustering...")
    from clustering import normalize, cluster_calls, cluster_vowels

    X_scaled, scaler = normalize(feature_matrix.copy(), metadata, feature_names)
    labels, probabilities, gmm, optimal_k = cluster_calls(X_scaled)
    vowel_labels, vowel_gmm, vowel_mask = cluster_vowels(feature_matrix, feature_names)
    metadata = metadata.copy()
    metadata['cluster'] = labels
    print(f"  {optimal_k} call types found.")

    # ── Stage 3: Statistical Analysis ───────────────────────────────────────
    print("\nStage 3: Statistical analysis...")
    from analysis import (
        build_sequences, compute_pmi_matrix, build_transition_matrix,
        row_entropies, analyze_regional_variation, detect_name_candidates, infer_herds,
    )

    sequences = build_sequences(labels, metadata)
    pmi_matrix, ctx_names = compute_pmi_matrix(labels, metadata['context'].values, optimal_k)
    trans_matrix = build_transition_matrix(sequences, optimal_k)
    entropies_arr = row_entropies(trans_matrix)
    regional_df = analyze_regional_variation(labels, metadata, optimal_k)
    name_candidates = detect_name_candidates(labels, metadata, optimal_k)
    herd_map = infer_herds(metadata)

    # ── Stage 4: Classification ─────────────────────────────────────────────
    print("\nStage 4: Training classifiers...")
    from classification import train_classifiers, feature_importances

    # Need minimum 5 samples per context for stratified train/test split
    ctx_counts = metadata['context'].value_counts()
    rare = ctx_counts[ctx_counts < 5].index.tolist()
    if rare:
        print(f"  Dropping {len(rare)} contexts with <2 samples: {rare}")
        mask = ~metadata['context'].isin(rare)
        feature_matrix = feature_matrix[mask.values]
        X_scaled = X_scaled[mask.values]
        labels = labels[mask.values]
        metadata = metadata[mask].reset_index(drop=True)

    context_clf, valence_clf, arousal_clf, cv_scores = train_classifiers(
        X_scaled, metadata, feature_names
    )
    print("\n  Top 5 features predicting behavioral context:")
    for name, imp in feature_importances(context_clf, feature_names, top_n=5):
        print(f"    {name}: {imp:.3f}")

    # ── Stage 5: Inference ──────────────────────────────────────────────────
    print("\nStage 5: Generating interpretations...")
    from inference import process_full_dataset, print_call_report

    results_df = process_full_dataset(
        feature_matrix, metadata, scaler, gmm,
        context_clf, valence_clf, arousal_clf, name_candidates
    )
    out_csv = os.path.join(OUTPUT_DIR, 'call_interpretations.csv')
    results_df.to_csv(out_csv, index=False)
    print(f"  Saved {len(results_df)} interpretations -> {out_csv}")

    print("\n-- Sample interpretations (first 3 calls) --")
    for _, row in results_df.head(3).iterrows():
        print_call_report(row.to_dict())

    # ── Stage 5b: Advanced Inference ────────────────────────────────────────
    print("\n" + "=" * 70)
    print("Stage 5b: Advanced inference (voice profiles + affinity)")
    print("=" * 70)
    from advanced_inference import (
        train_caller_classifier, build_voice_profiles, caller_identifiability,
        build_enhanced_features, train_enhanced_context, caller_context_affinity,
        CallSimilaritySearch,
    )

    caller_clf, _, caller_cv, known_callers = train_caller_classifier(X_scaled, metadata)
    voice_profiles = build_voice_profiles(feature_matrix, metadata, feature_names)
    identifiability = caller_identifiability(feature_matrix, metadata)
    X_enhanced, _, _ = build_enhanced_features(X_scaled, metadata)
    enhanced_ctx_clf = train_enhanced_context(X_enhanced, metadata)
    affinity_df = caller_context_affinity(metadata)

    if not voice_profiles.empty:
        voice_profiles.to_csv(os.path.join(OUTPUT_DIR, 'voice_profiles.csv'))
    if not identifiability.empty:
        identifiability.to_csv(os.path.join(OUTPUT_DIR, 'caller_identifiability.csv'), index=False)
    if not affinity_df.empty:
        affinity_df.to_csv(os.path.join(OUTPUT_DIR, 'caller_context_affinity.csv'), index=False)

    # ── Stage 6: Visualizations + Export ────────────────────────────────────
    print("\nStage 6: Export frontend data...")
    from visualize import embed_2d
    from export_frontend import export_all

    coords_2d = embed_2d(X_scaled)

    export_all(
        target_dir=FRONTEND_DATA_DIR,
        feature_matrix=feature_matrix,
        feature_names=feature_names,
        metadata=metadata,
        X_scaled=X_scaled,
        coords_2d=coords_2d,
        labels=labels,
        pmi_matrix=pmi_matrix,
        context_names=ctx_names,
        transition_matrix=trans_matrix,
        k_opt=optimal_k,
        results_df=results_df,
        voice_profiles=voice_profiles,
        identifiability_df=identifiability,
        affinity_df=affinity_df,
        cv_scores=cv_scores,
        caller_cv_score=caller_cv,
        known_callers=known_callers,
        output_csv_dir=OUTPUT_DIR,
    )

    # Save models
    model_path = os.path.join(OUTPUT_DIR, 'models.joblib')
    joblib.dump({
        'scaler': scaler, 'gmm': gmm,
        'context_clf': context_clf, 'valence_clf': valence_clf, 'arousal_clf': arousal_clf,
        'feature_names': feature_names, 'optimal_k': optimal_k,
    }, model_path)

    print(f"\nModels saved -> {model_path}")
    print(f"Frontend data -> {FRONTEND_DATA_DIR}/")
    print(f"\nDone! Serve frontend: cd frontend && python -m http.server 8000")
    return results_df


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Tusk and Tidy — Real Data Pipeline')
    parser.add_argument('--max-segments', type=int, default=None,
                        help='Limit segments for quick test (e.g. 200)')
    parser.add_argument('--no-plots', action='store_true')
    args = parser.parse_args()

    run(max_segments=args.max_segments, no_plots=args.no_plots)
