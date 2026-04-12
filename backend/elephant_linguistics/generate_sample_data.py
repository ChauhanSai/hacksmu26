"""
Generate realistic sample data for testing the pipeline without audio files.
Produces sample_data/features.csv with pre-extracted acoustic features + metadata.
Run: python generate_sample_data.py
"""

import numpy as np
import pandas as pd
import os

rng = np.random.default_rng(42)

CONTEXTS = [
    'Affiliative', 'Aggressive', 'Protest & Distress',
    'Calf Reassurance & Protection', 'Calf Nourishment & Weaning',
    'Foraging & Comfort Technique', 'Courtship', 'Advertisement & Attraction',
    'Coalition Building', 'Conflict & Confrontation', 'Attentive',
    'Avoidance', 'Maintenance', 'Birth', 'Lone & Object Play',
]

AGE_SEX = ['adult_female', 'adult_male', 'calf', 'subadult_female', 'subadult_male']
BODY_PARTS = ['trunk', 'ears', 'feet', 'mouth', 'body']
COMM_MODES = ['acoustic', 'seismic', 'visual', 'chemical']
SOUND_TYPES = ['rumble', 'trumpet', 'roar', 'bark', 'chirp']
COUNTRIES = ['Kenya', 'Botswana', 'South Africa', 'Zimbabwe', 'Tanzania']

# Acoustic feature distributions per context (mean offsets from baseline)
# Tuned to make contexts separable in feature space
CONTEXT_PROFILES = {
    'Affiliative':                    {'mean_f0': 14, 'rms_energy': 0.02, 'mean_hnr': 8,  'duration': 3.0},
    'Aggressive':                     {'mean_f0': 22, 'rms_energy': 0.08, 'mean_hnr': 3,  'duration': 1.5},
    'Protest & Distress':             {'mean_f0': 28, 'rms_energy': 0.10, 'mean_hnr': 2,  'duration': 2.0},
    'Calf Reassurance & Protection':  {'mean_f0': 16, 'rms_energy': 0.03, 'mean_hnr': 7,  'duration': 3.5},
    'Calf Nourishment & Weaning':     {'mean_f0': 18, 'rms_energy': 0.025,'mean_hnr': 6,  'duration': 2.5},
    'Foraging & Comfort Technique':   {'mean_f0': 12, 'rms_energy': 0.015,'mean_hnr': 9,  'duration': 4.0},
    'Courtship':                      {'mean_f0': 20, 'rms_energy': 0.05, 'mean_hnr': 5,  'duration': 5.0},
    'Advertisement & Attraction':     {'mean_f0': 25, 'rms_energy': 0.07, 'mean_hnr': 4,  'duration': 4.5},
    'Coalition Building':             {'mean_f0': 15, 'rms_energy': 0.03, 'mean_hnr': 8,  'duration': 3.2},
    'Conflict & Confrontation':       {'mean_f0': 24, 'rms_energy': 0.09, 'mean_hnr': 2,  'duration': 1.8},
    'Attentive':                      {'mean_f0': 13, 'rms_energy': 0.01, 'mean_hnr': 10, 'duration': 2.0},
    'Avoidance':                      {'mean_f0': 19, 'rms_energy': 0.06, 'mean_hnr': 3,  'duration': 1.2},
    'Maintenance':                    {'mean_f0': 11, 'rms_energy': 0.01, 'mean_hnr': 11, 'duration': 4.8},
    'Birth':                          {'mean_f0': 30, 'rms_energy': 0.12, 'mean_hnr': 2,  'duration': 2.5},
    'Lone & Object Play':             {'mean_f0': 17, 'rms_energy': 0.04, 'mean_hnr': 6,  'duration': 2.8},
}


def make_row(context: str, session_id: str, call_idx: int,
              elephant_id: str = None, elephant_voice: dict = None) -> dict:
    p = CONTEXT_PROFILES[context]

    # Individual voice fingerprint offsets (small, systematic per-elephant)
    voice = elephant_voice or {}
    f0_bias     = voice.get('f0_bias', 0)
    formant_bias= voice.get('formant_bias', 0)
    hnr_bias    = voice.get('hnr_bias', 0)
    duration_bias = voice.get('duration_bias', 0)
    age_sex_pref  = voice.get('age_sex', None)

    age_sex = age_sex_pref or rng.choice(AGE_SEX)
    # Calves have higher F0 (smaller vocal tract)
    f0_offset = 5 if 'calf' in age_sex else (3 if 'subadult' in age_sex else 0)
    f0_base = p['mean_f0'] + f0_offset + f0_bias

    mean_f0 = max(5, rng.normal(f0_base, 1.8))
    std_f0  = rng.uniform(0.5, 3.0)

    return {
        # ── Metadata ────────────────────────────────────────────────────────
        'filename':    f"session_{session_id}_call_{call_idx:04d}.wav",
        'context':     context,
        'age_sex':     age_sex,
        'body_part':   rng.choice(BODY_PARTS),
        'comm_mode':   rng.choice(COMM_MODES, p=[0.7, 0.1, 0.15, 0.05]),
        'sound_type':  rng.choice(SOUND_TYPES, p=[0.6, 0.15, 0.1, 0.1, 0.05]),
        'elephant_id': elephant_id or f"E{rng.integers(1, 25):03d}",
        'receiver_id': f"E{rng.integers(1, 25):03d}" if rng.random() > 0.4 else None,
        'country':     voice.get('country') or rng.choice(COUNTRIES),
        'session_id':  session_id,
        # ── F0 features (1-4) ───────────────────────────────────────────────
        'mean_f0':  round(mean_f0, 3),
        'std_f0':   round(std_f0, 3),
        'f0_range': round(rng.uniform(2, 15), 3),
        'f0_slope': round(rng.normal(0, 0.5), 4),
        # ── Formants (5-7) — biased by individual vocal tract ───────────────
        'mean_f1': round(rng.normal(80  + mean_f0 * 1.2 + formant_bias,       6), 2),
        'mean_f2': round(rng.normal(160 + mean_f0 * 0.8 + formant_bias * 1.5, 10), 2),
        'mean_f3': round(rng.normal(280 + mean_f0 * 0.5 + formant_bias * 2,   14), 2),
        # ── Temporal (8-10) ─────────────────────────────────────────────────
        'duration':          round(max(0.3, rng.normal(p['duration'] + duration_bias, 0.6)), 3),
        'attack_time':       round(rng.uniform(0.05, 0.6), 3),
        'temporal_centroid': round(rng.uniform(0.2, 0.8), 3),
        # ── Energy / noise (11-13) ──────────────────────────────────────────
        'rms_energy':       round(max(0.001, rng.normal(p['rms_energy'], p['rms_energy'] * 0.3)), 5),
        'mean_hnr':         round(rng.normal(p['mean_hnr'] + hnr_bias, 1.2), 3),
        'spectral_flatness':round(rng.uniform(0.001, 0.05), 5),
        # ── Spectral shape (14-16) ──────────────────────────────────────────
        'spectral_centroid':  round(rng.normal(mean_f0 * 3.5, 20), 2),
        'spectral_bandwidth': round(rng.normal(60, 10), 2),
        'spectral_rolloff':   round(rng.normal(mean_f0 * 6, 40), 2),
        # ── MFCCs (17-20) ───────────────────────────────────────────────────
        'mfcc_1': round(rng.normal(-80 + mean_f0 * 0.5, 8), 3),
        'mfcc_2': round(rng.normal(10,  5), 3),
        'mfcc_3': round(rng.normal(0,   4), 3),
        'mfcc_4': round(rng.normal(0,   3), 3),
    }


def _build_elephant_voices(n_elephants: int) -> dict:
    """Build stable voice fingerprints + context preferences per elephant."""
    voices = {}
    for i in range(n_elephants):
        eid = f"E{i+1:03d}"
        age_sex = rng.choice(AGE_SEX)
        voices[eid] = {
            'age_sex':       age_sex,
            'f0_bias':       rng.normal(0, 3),       # ±3 Hz individual offset
            'formant_bias':  rng.normal(0, 12),      # vocal tract shape
            'hnr_bias':      rng.normal(0, 2),       # tonal vs noisy voice
            'duration_bias': rng.normal(0, 0.5),     # tends to call long/short
            'country':       rng.choice(COUNTRIES),
            # Context preferences (each elephant has a few favorites)
            'preferred_contexts': list(rng.choice(CONTEXTS, size=3, replace=False)),
        }
    return voices


def generate(n_calls: int = 500, n_sessions: int = 25, n_elephants: int = 20,
             out_dir: str = 'sample_data'):
    os.makedirs(out_dir, exist_ok=True)
    rows = []
    calls_per_session = n_calls // n_sessions

    voices = _build_elephant_voices(n_elephants)
    eids = list(voices.keys())

    for s in range(n_sessions):
        session_id = f"{s+1:02d}"
        dominant_ctx = rng.choice(CONTEXTS)
        # Each session has ~3-5 participating elephants
        participants = rng.choice(eids, size=rng.integers(3, 6), replace=False).tolist()

        for c in range(calls_per_session):
            eid = rng.choice(participants)
            voice = voices[eid]

            # 50% chance: elephant vocalizes in a preferred context
            # 30% chance: session's dominant context
            # 20% chance: random
            r = rng.random()
            if r < 0.50:
                ctx = rng.choice(voice['preferred_contexts'])
            elif r < 0.80:
                ctx = dominant_ctx
            else:
                ctx = rng.choice(CONTEXTS)

            rows.append(make_row(ctx, session_id, c + 1, elephant_id=eid, elephant_voice=voice))

    df = pd.DataFrame(rows)
    out_path = os.path.join(out_dir, 'features.csv')
    df.to_csv(out_path, index=False)

    print(f"Generated {len(df)} sample calls → {out_path}")
    print(f"  {n_elephants} unique elephants, {n_sessions} sessions")
    print(f"  Calls per elephant: min={df['elephant_id'].value_counts().min()}, "
          f"max={df['elephant_id'].value_counts().max()}, "
          f"mean={df['elephant_id'].value_counts().mean():.1f}")
    print(f"  Context distribution:\n{df['context'].value_counts().to_string()}")
    return df


if __name__ == '__main__':
    generate()
