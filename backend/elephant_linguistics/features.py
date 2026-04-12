"""Stage 1: Acoustic feature extraction from segmented elephant call audio."""

import numpy as np
import librosa
import parselmouth
import pandas as pd
import os


def extract_features(y_segment: np.ndarray, sr: int) -> dict:
    """Extract 20 acoustic features from one segmented elephant call."""
    snd = parselmouth.Sound(y_segment, sampling_frequency=sr)

    # F0 (pitch_floor=5, pitch_ceiling=100 — critical for infrasonic calls)
    pitch = snd.to_pitch(time_step=0.01, pitch_floor=5, pitch_ceiling=100)
    f0 = pitch.selected_array['frequency']
    f0 = f0[f0 > 0]

    # Formants (maximum_formant=500 — critical, default 5500 Hz misses elephants)
    formants = snd.to_formant_burg(time_step=0.01, max_number_of_formants=5, maximum_formant=500)
    ts = formants.ts()
    f1 = [formants.get_value_at_time(1, t) for t in ts]
    f2 = [formants.get_value_at_time(2, t) for t in ts]
    f3 = [formants.get_value_at_time(3, t) for t in ts]

    # HNR
    harmonicity = snd.to_harmonicity()
    hnr_vals = harmonicity.values[harmonicity.values != -200]

    # Temporal envelope
    env = np.abs(y_segment)
    smooth = np.convolve(env, np.ones(sr // 10) / (sr // 10), mode='same')

    features = {
        # F0 (1-4)
        'mean_f0':    np.mean(f0) if len(f0) > 0 else 0,
        'std_f0':     np.std(f0) if len(f0) > 0 else 0,
        'f0_range':   float(np.max(f0) - np.min(f0)) if len(f0) > 0 else 0,
        'f0_slope':   float(np.polyfit(np.arange(len(f0)), f0, 1)[0]) if len(f0) > 1 else 0,
        # Formants (5-7)
        'mean_f1': float(np.nanmean(f1)),
        'mean_f2': float(np.nanmean(f2)),
        'mean_f3': float(np.nanmean(f3)),
        # Temporal (8-10)
        'duration':          len(y_segment) / sr,
        'attack_time':       float(np.argmax(smooth) / sr),
        'temporal_centroid': float(np.sum(np.arange(len(smooth)) * smooth) / np.sum(smooth) / sr),
        # Energy/noise (11-13)
        'rms_energy':      float(np.sqrt(np.mean(y_segment ** 2))),
        'mean_hnr':        float(np.mean(hnr_vals)) if len(hnr_vals) > 0 else 0,
        'spectral_flatness': float(np.mean(librosa.feature.spectral_flatness(y=y_segment))),
        # Spectral shape (14-16)
        'spectral_centroid':  float(np.mean(librosa.feature.spectral_centroid(y=y_segment, sr=sr))),
        'spectral_bandwidth': float(np.mean(librosa.feature.spectral_bandwidth(y=y_segment, sr=sr))),
        'spectral_rolloff':   float(np.mean(librosa.feature.spectral_rolloff(y=y_segment, sr=sr, roll_percent=0.85))),
        # MFCCs (17-20) — fmin=5, fmax=500, n_fft=8192 critical
        'mfcc_1': 0.0, 'mfcc_2': 0.0, 'mfcc_3': 0.0, 'mfcc_4': 0.0,
    }

    mfccs = librosa.feature.mfcc(y=y_segment, sr=sr, n_mfcc=4,
                                  n_fft=8192, hop_length=512, fmin=5, fmax=500)
    for i in range(4):
        features[f'mfcc_{i+1}'] = float(np.mean(mfccs[i]))

    return features


def process_all_calls(audio_dir: str, metadata_df: pd.DataFrame):
    """Process all segmented calls and align with metadata.

    Returns:
        feature_matrix: np.ndarray shape (N, 20)
        feature_names: list of str
        metadata: aligned DataFrame
    """
    all_features = []
    valid_indices = []

    for idx, row in metadata_df.iterrows():
        filepath = os.path.join(audio_dir, row['filename'])
        try:
            y, sr = librosa.load(filepath, sr=None)
            all_features.append(extract_features(y, sr))
            valid_indices.append(idx)
        except Exception as e:
            print(f"Skipping {row['filename']}: {e}")

    feature_df = pd.DataFrame(all_features)
    return feature_df.values, list(feature_df.columns), metadata_df.loc[valid_indices].reset_index(drop=True)
