"""Stage 6: Aggregate reports and visualizations."""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # non-interactive backend — never blocks on plt.show()
import matplotlib.pyplot as plt
import seaborn as sns


def repertoire_report(labels: np.ndarray, optimal_k: int, pmi_matrix: np.ndarray, context_names: list) -> str:
    lines = [f"FINDING: {optimal_k} acoustically distinct call types identified.\n"]
    for s in range(optimal_k):
        top_ctx_idx = int(np.argmax(pmi_matrix[s]))
        top_pmi     = pmi_matrix[s][top_ctx_idx]
        top_ctx     = context_names[top_ctx_idx]
        count       = int(np.sum(labels == s))
        if top_pmi > 2.0:
            tag = "CONTEXT-SPECIFIC"
        elif top_pmi > 1.0:
            tag = "MODERATELY SPECIFIC"
        else:
            tag = "GENERAL PURPOSE"
        lines.append(f"  Symbol {s:>3}: n={count:>5}, top={top_ctx} (PMI={top_pmi:.2f}), {tag}")
    return '\n'.join(lines)


def emotion_report(feature_names: list, valence_clf, arousal_clf) -> str:
    lines = ["FINDING: Acoustic features encoding emotional valence and arousal:\n"]
    v_imp = sorted(zip(feature_names, valence_clf.feature_importances_), key=lambda x: -x[1])
    a_imp = sorted(zip(feature_names, arousal_clf.feature_importances_), key=lambda x: -x[1])

    lines.append("  Top valence predictors:")
    for name, imp in v_imp[:5]:
        lines.append(f"    {name}: {imp:.3f}")

    lines.append("\n  Top arousal predictors:")
    for name, imp in a_imp[:5]:
        lines.append(f"    {name}: {imp:.3f}")

    lines.append(f"\n  INTERPRETATION: Valence primarily encoded by {v_imp[0][0]}, "
                 f"arousal by {a_imp[0][0]} — analogous to prosodic cues in human speech.")
    return '\n'.join(lines)


# ── Visualizations ────────────────────────────────────────────────────────────

def plot_pmi_heatmap(pmi_matrix: np.ndarray, context_names: list, output_path: str = None):
    fig, ax = plt.subplots(figsize=(14, max(6, len(pmi_matrix) // 3)))
    sns.heatmap(pmi_matrix, xticklabels=context_names, yticklabels=[f"S{i}" for i in range(len(pmi_matrix))],
                cmap='RdYlGn', center=0, ax=ax)
    ax.set_title("PMI: Symbol–Behavioral Context Associations")
    ax.set_xlabel("Behavioral Context")
    ax.set_ylabel("Call Symbol")
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150)
    plt.close(fig)


def plot_vowel_space(feature_matrix: np.ndarray, feature_names: list, vowel_labels: np.ndarray,
                     clean_mask: np.ndarray, output_path: str = None):
    f1_idx = feature_names.index('mean_f1')
    f2_idx = feature_names.index('mean_f2')
    f1f2   = feature_matrix[clean_mask][:, [f1_idx, f2_idx]]

    fig, ax = plt.subplots(figsize=(8, 6))
    scatter = ax.scatter(f1f2[:, 1], f1f2[:, 0], c=vowel_labels, cmap='tab10', alpha=0.6, s=20)
    ax.invert_xaxis()
    ax.invert_yaxis()
    ax.set_xlabel("F2 (Hz)")
    ax.set_ylabel("F1 (Hz)")
    ax.set_title("Elephant 'Vowel Space' (F1/F2 Clusters)")
    plt.colorbar(scatter, ax=ax, label='Vowel cluster')
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150)
    plt.close(fig)


def plot_transition_matrix(transition_matrix: np.ndarray, output_path: str = None):
    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(transition_matrix, cmap='Blues', ax=ax, vmin=0, vmax=1)
    ax.set_title("Symbol Transition Probabilities")
    ax.set_xlabel("Next Symbol")
    ax.set_ylabel("Current Symbol")
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150)
    plt.close(fig)


def plot_confusion_matrix(cm: np.ndarray, labels: list, output_path: str = None):
    fig, ax = plt.subplots(figsize=(12, 10))
    sns.heatmap(cm, xticklabels=labels, yticklabels=labels, fmt='d', cmap='Blues', ax=ax)
    ax.set_title("Context Classifier Confusion Matrix")
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    plt.tight_layout()
    if output_path:
        plt.savefig(output_path, dpi=150)
    plt.close(fig)
