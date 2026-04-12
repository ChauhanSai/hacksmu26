"""
Pipeline runner that starts from a pre-extracted features CSV (no audio files needed).
Runs Stages 2-6.

Usage:
    python run_from_csv.py --csv sample_data/features.csv
    python run_from_csv.py --csv sample_data/features.csv --output-dir output
"""

import argparse
import os
import joblib
import numpy as np
import pandas as pd

from clustering import normalize, cluster_calls, cluster_vowels
from analysis import (
    build_sequences, compute_pmi_matrix, build_transition_matrix,
    row_entropies, analyze_regional_variation, detect_name_candidates, infer_herds,
)
from classification import train_classifiers, feature_importances
from inference import process_full_dataset, print_call_report
from advanced_inference import (
    train_caller_classifier, build_voice_profiles, caller_identifiability,
    build_enhanced_features, train_enhanced_context, caller_context_affinity,
    CallSimilaritySearch, full_call_inference, print_full_inference,
)
from reports import (
    repertoire_report, emotion_report,
    plot_pmi_heatmap, plot_vowel_space, plot_transition_matrix,
)

FEATURE_COLS = [
    'mean_f0', 'std_f0', 'f0_range', 'f0_slope',
    'mean_f1', 'mean_f2', 'mean_f3',
    'duration', 'attack_time', 'temporal_centroid',
    'rms_energy', 'mean_hnr', 'spectral_flatness',
    'spectral_centroid', 'spectral_bandwidth', 'spectral_rolloff',
    'mfcc_1', 'mfcc_2', 'mfcc_3', 'mfcc_4',
]


def run(csv_path: str, output_dir: str = 'output', show_plots: bool = True):
    os.makedirs(output_dir, exist_ok=True)

    # ── Load CSV ─────────────────────────────────────────────────────────────
    print(f"Loading {csv_path} ...")
    df = pd.read_csv(csv_path)
    print(f"  {len(df)} calls, columns: {list(df.columns)}")

    feature_names  = [c for c in FEATURE_COLS if c in df.columns]
    feature_matrix = df[feature_names].values.astype(float)
    metadata       = df.drop(columns=feature_names)

    print(f"  Feature matrix: {feature_matrix.shape}")

    # ── Stage 2: Normalize + Cluster ─────────────────────────────────────────
    print("\nStage 2: Normalizing and clustering...")
    X_scaled, scaler = normalize(feature_matrix.copy(), metadata, feature_names)
    labels, probabilities, gmm, optimal_k = cluster_calls(X_scaled)
    vowel_labels, vowel_gmm, vowel_mask = cluster_vowels(feature_matrix, feature_names)
    metadata = metadata.copy()
    metadata['cluster'] = labels
    print(f"  {optimal_k} call types found.")

    # ── Stage 3: Statistical Analysis ────────────────────────────────────────
    print("\nStage 3: Statistical analysis...")
    sequences        = build_sequences(labels, metadata)
    pmi_matrix, ctx_names = compute_pmi_matrix(labels, metadata['context'].values, optimal_k)
    trans_matrix          = build_transition_matrix(sequences, optimal_k)
    entropies_arr         = row_entropies(trans_matrix)
    regional_df           = analyze_regional_variation(labels, metadata, optimal_k)
    name_candidates       = detect_name_candidates(labels, metadata, optimal_k)
    herd_map              = infer_herds(metadata)

    if regional_df is not None:
        universal = regional_df[regional_df['type'] == 'UNIVERSAL'].shape[0]
        regional  = regional_df[regional_df['type'] == 'REGIONAL'].shape[0]
        print(f"  Regional analysis: {universal} universal, {regional} regional symbols")

    if name_candidates is not None and not name_candidates.empty:
        print(f"  Name candidates found: {len(name_candidates)}")

    # ── Stage 4: Classification ───────────────────────────────────────────────
    print("\nStage 4: Training classifiers...")
    context_clf, valence_clf, arousal_clf, cv_scores = train_classifiers(
        X_scaled, metadata, feature_names
    )
    print("\n  Top 5 features predicting behavioral context:")
    for name, imp in feature_importances(context_clf, feature_names, top_n=5):
        print(f"    {name}: {imp:.3f}")

    # ── Stage 5: Inference ────────────────────────────────────────────────────
    print("\nStage 5: Generating interpretations...")
    results_df = process_full_dataset(
        feature_matrix, metadata, scaler, gmm,
        context_clf, valence_clf, arousal_clf, name_candidates
    )
    out_csv = os.path.join(output_dir, 'call_interpretations.csv')
    results_df.to_csv(out_csv, index=False)
    print(f"  Saved {len(results_df)} interpretations → {out_csv}")

    print("\n── Sample interpretations (first 3 calls) ──")
    for _, row in results_df.head(3).iterrows():
        print_call_report(row.to_dict())

    # ── Stage 5b: Advanced Inference (caller ID + enhanced context) ──────────
    print("\n" + "=" * 70)
    print("Stage 5b: Advanced inference (caller identification + voice profiles)")
    print("=" * 70)

    caller_clf, _, caller_cv, known_callers = train_caller_classifier(X_scaled, metadata)
    voice_profiles    = build_voice_profiles(feature_matrix, metadata, feature_names)
    identifiability   = caller_identifiability(feature_matrix, metadata)
    X_enhanced, _, _  = build_enhanced_features(X_scaled, metadata)
    enhanced_ctx_clf  = train_enhanced_context(X_enhanced, metadata)
    affinity_df       = caller_context_affinity(metadata)
    similarity_search = CallSimilaritySearch(X_scaled, metadata, k=5)

    # Save everything
    if not voice_profiles.empty:
        voice_profiles.to_csv(os.path.join(output_dir, 'voice_profiles.csv'))
    if not identifiability.empty:
        identifiability.to_csv(os.path.join(output_dir, 'caller_identifiability.csv'), index=False)
        print(f"\n  Top 5 most acoustically distinctive callers:")
        for _, row in identifiability.head(5).iterrows():
            print(f"    {row['elephant_id']}: identifiability={row['identifiability']:.2f} "
                  f"(n={int(row['n_calls'])})")
    if not affinity_df.empty:
        affinity_df.to_csv(os.path.join(output_dir, 'caller_context_affinity.csv'), index=False)
        print(f"\n  Top 3 specialist callers (most context-deviant):")
        for _, row in affinity_df.head(3).iterrows():
            print(f"    {row['elephant_id']} (n={int(row['n_calls'])}): {row['top_contexts']}")

    # Run full inference on first 3 calls as demo
    print("\n── Full call inference examples (who + what + why) ──")
    for idx in range(min(3, len(metadata))):
        report = full_call_inference(
            idx, X_scaled, metadata, caller_clf, enhanced_ctx_clf,
            X_enhanced, similarity_search, voice_profiles,
        )
        print_full_inference(report)

    # ── Stage 6: Reports ─────────────────────────────────────────────────────
    print("\nStage 6: Reports and visualizations...")
    print("\n" + repertoire_report(labels, optimal_k, pmi_matrix, ctx_names))
    print("\n" + emotion_report(feature_names, valence_clf, arousal_clf))

    if show_plots:
        plot_pmi_heatmap(pmi_matrix, ctx_names, os.path.join(output_dir, 'pmi_heatmap.png'))
        plot_vowel_space(feature_matrix, feature_names, vowel_labels, vowel_mask,
                         os.path.join(output_dir, 'vowel_space.png'))
        plot_transition_matrix(trans_matrix, os.path.join(output_dir, 'transitions.png'))

    # ── Interactive visualization ─────────────────────────────────────────────
    print("\nBuilding interactive visualization...")
    from visualize import build_viz, embed_2d
    build_viz(csv_path, os.path.join(output_dir, 'visualization.html'))

    # ── Export frontend-ready data ────────────────────────────────────────────
    print("\nExporting frontend data...")
    from export_frontend import export_all

    coords_2d = embed_2d(X_scaled)
    frontend_data_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', '..', 'frontend', 'data')
    )
    export_all(
        target_dir=frontend_data_dir,
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
        output_csv_dir=output_dir,
    )

    # ── Save models ───────────────────────────────────────────────────────────
    model_path = os.path.join(output_dir, 'models.joblib')
    joblib.dump({
        'scaler': scaler, 'gmm': gmm,
        'context_clf': context_clf, 'valence_clf': valence_clf, 'arousal_clf': arousal_clf,
        'feature_names': feature_names, 'optimal_k': optimal_k,
    }, model_path)
    print(f"\nModels saved → {model_path}")
    print(f"Done. All outputs in {output_dir}/")
    return results_df


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv',        required=True, help='Path to features CSV')
    parser.add_argument('--output-dir', default='output')
    parser.add_argument('--no-plots',   action='store_true', help='Skip matplotlib plots')
    args = parser.parse_args()

    run(args.csv, args.output_dir, show_plots=not args.no_plots)
