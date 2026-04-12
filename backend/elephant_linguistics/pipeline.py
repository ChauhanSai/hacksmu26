"""Full pipeline runner for the Elephant Communication Decoder."""

import argparse
import joblib
import os
import pandas as pd

from data_loader import download_dataset, load_metadata
from features import process_all_calls
from clustering import normalize, cluster_calls, cluster_vowels
from analysis import (
    build_sequences, compute_pmi_matrix, build_transition_matrix,
    row_entropies, analyze_regional_variation, detect_name_candidates, infer_herds,
)
from classification import train_classifiers, feature_importances
from inference import process_full_dataset, print_call_report
from reports import (
    repertoire_report, emotion_report,
    plot_pmi_heatmap, plot_vowel_space, plot_transition_matrix, plot_confusion_matrix,
)


def run(audio_dir: str, metadata_path: str, output_dir: str = 'output'):
    os.makedirs(output_dir, exist_ok=True)

    # ── Stage 1: Feature extraction ──────────────────────────────────────────
    print("Stage 1: Extracting features...")
    metadata = load_metadata(metadata_path)
    feature_matrix, feature_names, metadata = process_all_calls(audio_dir, metadata)
    print(f"  {len(feature_matrix)} calls processed, {len(feature_names)} features each.")

    # ── Stage 2: Normalize + cluster ─────────────────────────────────────────
    print("Stage 2: Normalizing and clustering...")
    X_scaled, scaler = normalize(feature_matrix.copy(), metadata, feature_names)
    labels, probabilities, gmm, optimal_k = cluster_calls(X_scaled)
    vowel_labels, vowel_gmm, vowel_mask = cluster_vowels(feature_matrix, feature_names)

    # ── Stage 3: Statistical analysis ────────────────────────────────────────
    print("Stage 3: Statistical analysis...")
    sequences        = build_sequences(labels, metadata)
    pmi_matrix, ctx_names = compute_pmi_matrix(labels, metadata['context'].values, optimal_k)
    transition_matrix     = build_transition_matrix(sequences, optimal_k)
    entropies             = row_entropies(transition_matrix)
    regional_df           = analyze_regional_variation(labels, metadata, optimal_k)
    name_candidates       = detect_name_candidates(labels, metadata, optimal_k)
    herd_map              = infer_herds(metadata)

    # ── Stage 4: Classification ───────────────────────────────────────────────
    print("Stage 4: Training classifiers...")
    context_clf, valence_clf, arousal_clf, cv_scores = train_classifiers(X_scaled, metadata, feature_names)

    print("  Top context predictors:", feature_importances(context_clf, feature_names))

    # ── Stage 5: Inference ────────────────────────────────────────────────────
    print("Stage 5: Generating interpretations...")
    results_df = process_full_dataset(
        feature_matrix, metadata, scaler, gmm,
        context_clf, valence_clf, arousal_clf, name_candidates
    )
    results_df.to_csv(os.path.join(output_dir, 'call_interpretations.csv'), index=False)

    # Print first 5 calls
    for _, row in results_df.head(5).iterrows():
        print_call_report(row.to_dict())

    # ── Stage 6: Reports + visualizations ────────────────────────────────────
    print("\nStage 6: Generating reports...")
    print(repertoire_report(labels, optimal_k, pmi_matrix, ctx_names))
    print(emotion_report(feature_names, valence_clf, arousal_clf))

    plot_pmi_heatmap(pmi_matrix, ctx_names, os.path.join(output_dir, 'pmi_heatmap.png'))
    plot_vowel_space(feature_matrix, feature_names, vowel_labels, vowel_mask,
                     os.path.join(output_dir, 'vowel_space.png'))
    plot_transition_matrix(transition_matrix, os.path.join(output_dir, 'transitions.png'))

    # ── Persist models ────────────────────────────────────────────────────────
    joblib.dump({'scaler': scaler, 'gmm': gmm, 'context_clf': context_clf,
                 'valence_clf': valence_clf, 'arousal_clf': arousal_clf,
                 'feature_names': feature_names, 'optimal_k': optimal_k},
                os.path.join(output_dir, 'models.joblib'))

    print(f"\nDone. Results saved to {output_dir}/")
    return results_df


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Elephant Communication Decoder')
    parser.add_argument('--audio-dir',      required=True, help='Directory of .wav files')
    parser.add_argument('--metadata',       required=True, help='CSV/JSON metadata file')
    parser.add_argument('--output-dir',     default='output')
    parser.add_argument('--gcs-bucket',     help='GCS bucket name (optional, triggers download)')
    parser.add_argument('--gcs-prefix',     default='calls/')
    args = parser.parse_args()

    if args.gcs_bucket:
        print(f"Downloading from gs://{args.gcs_bucket}/{args.gcs_prefix} ...")
        download_dataset(args.gcs_bucket, args.gcs_prefix, args.audio_dir)

    run(args.audio_dir, args.metadata, args.output_dir)
