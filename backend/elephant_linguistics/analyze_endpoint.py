"""
Flask endpoint: POST /api/analyze
Accepts a WAV file, extracts features, runs inference, returns a full report JSON.
"""

import os
import sys
import io
import json
import tempfile
import numpy as np
import librosa
import joblib
import warnings
warnings.filterwarnings('ignore')

from flask import Flask, request, jsonify
from flask_cors import CORS

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(__file__))
from features import extract_features

app = Flask(__name__)
CORS(app)

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'output', 'models.joblib')

# Interpretation templates (subset for quick inference)
INTERP = {
    'Affiliative': 'engaging in social bonding or friendly contact',
    'Aggressive': 'displaying aggressive or threatening behavior',
    'Protest & Distress': 'in distress or protesting a situation',
    'Calf Reassurance & Protection': 'providing reassurance or protection to a calf',
    'Calf Nourishment & Weaning': 'signaling related to nursing or feeding',
    'Foraging & Comfort Technique': 'signaling interest in food or foraging',
    'Courtship': 'producing courtship or mating vocalizations',
    'Advertisement & Attraction': 'producing an advertisement call to attract attention',
    'Coalition Building': 'coordinating with others, building alliances',
    'Conflict & Confrontation': 'involved in an active conflict or confrontation',
    'Attacking & Mobbing': 'involved in attack or group mobbing behavior',
    'Attentive': 'in an alert, attentive state — listening or monitoring',
    'Avoidance': 'signaling avoidance or retreat',
    'Ambivalent': 'in a mixed or uncertain emotional state',
    'Birth': 'vocalizing in association with a birth event',
    'Death': 'vocalizing in association with a death event — possible mourning',
    'Lone & Object Play': 'vocalizing during solitary play',
    'Maintenance': 'producing routine maintenance vocalizations',
    'Social Play': 'vocalizing during social play with other elephants',
    'Movement Space & Leadership': 'coordinating group movement or leadership',
    'Novel & Idiosyncratic': 'producing an unusual or individually learned call',
    'Submissive': 'producing a submissive vocalization',
    'Vigilance': 'in a vigilant state, monitoring for threats',
}

VALENCE_MAP = {
    'positive': ['Affiliative', 'Coalition Building', 'Courtship',
                 'Calf Reassurance & Protection', 'Lone & Object Play',
                 'Calf Nourishment & Weaning', 'Social Play'],
    'negative': ['Aggressive', 'Conflict & Confrontation', 'Protest & Distress',
                 'Attacking & Mobbing', 'Avoidance', 'Death', 'Submissive'],
}

AROUSAL_MAP = {
    'high': ['Aggressive', 'Attacking & Mobbing', 'Birth', 'Death',
             'Protest & Distress', 'Conflict & Confrontation',
             'Advertisement & Attraction', 'Vigilance'],
    'low': ['Affiliative', 'Foraging & Comfort Technique', 'Maintenance',
            'Lone & Object Play', 'Attentive', 'Ambivalent', 'Submissive'],
}


def get_valence(ctx):
    for v, ctxs in VALENCE_MAP.items():
        if ctx in ctxs:
            return v
    return 'neutral'


def get_arousal(ctx):
    for a, ctxs in AROUSAL_MAP.items():
        if ctx in ctxs:
            return a
    return 'medium'


def describe_f0(f0):
    if f0 < 15:
        return 'deep infrasonic rumble (below human hearing)'
    elif f0 < 30:
        return 'low infrasonic vocalization (barely perceptible to humans)'
    elif f0 < 60:
        return 'mid-range elephant vocalization'
    else:
        return 'higher-pitched call (audible to humans)'


def describe_hnr(hnr):
    if hnr > 10:
        return 'highly tonal and harmonic — a clear, structured call'
    elif hnr > 5:
        return 'moderately harmonic with some noise components'
    else:
        return 'noisy or broadband — less structured vocalization'


def describe_duration(dur):
    if dur < 1:
        return 'short burst vocalization'
    elif dur < 3:
        return 'moderate-length call'
    else:
        return 'sustained, long vocalization'


def describe_energy(rms):
    if rms > 0.05:
        return 'high intensity — likely a loud, forceful call'
    elif rms > 0.01:
        return 'moderate intensity'
    else:
        return 'quiet, low-energy vocalization'


@app.route('/api/analyze', methods=['POST'])
def analyze():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400

    audio_file = request.files['audio']

    # Save to temp
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        audio_file.save(tmp.name)
        tmp_path = tmp.name

    try:
        y, sr = librosa.load(tmp_path, sr=None)
        duration = len(y) / sr

        # Extract features
        feats = extract_features(y, sr)

        # Load models if available
        report = {
            'duration': round(duration, 3),
            'sample_rate': sr,
            'features': {k: round(v, 4) if isinstance(v, float) else v for k, v in feats.items()},
        }

        # Feature descriptions
        report['feature_descriptions'] = {
            'pitch': describe_f0(feats['mean_f0']),
            'harmonicity': describe_hnr(feats['mean_hnr']),
            'duration': describe_duration(feats['duration']),
            'energy': describe_energy(feats['rms_energy']),
        }

        # Try model inference
        if os.path.exists(MODEL_PATH):
            models = joblib.load(MODEL_PATH)
            scaler = models['scaler']
            gmm = models['gmm']
            context_clf = models['context_clf']
            valence_clf = models['valence_clf']
            arousal_clf = models['arousal_clf']
            feature_names = models['feature_names']

            fv = np.array([[feats.get(f, 0) for f in feature_names]])
            fv_scaled = scaler.transform(fv)

            # Cluster
            cluster = int(gmm.predict(fv_scaled)[0])
            cluster_prob = float(np.max(gmm.predict_proba(fv_scaled)[0]))

            # Context
            ctx_probs = context_clf.predict_proba(fv_scaled)[0]
            ctx_labels = context_clf.classes_
            sorted_idx = np.argsort(ctx_probs)[::-1]

            top_contexts = []
            for i in range(min(5, len(sorted_idx))):
                idx = sorted_idx[i]
                top_contexts.append({
                    'context': ctx_labels[idx],
                    'probability': round(float(ctx_probs[idx]) * 100, 1),
                })

            top_ctx = ctx_labels[sorted_idx[0]]
            top_prob = float(ctx_probs[sorted_idx[0]])

            # Valence/arousal
            val_pred = valence_clf.predict(fv_scaled)[0]
            aro_pred = arousal_clf.predict(fv_scaled)[0]

            report['cluster'] = cluster
            report['cluster_confidence'] = round(cluster_prob * 100, 1)
            report['top_contexts'] = top_contexts
            report['valence'] = val_pred
            report['arousal'] = aro_pred

            # Build interpretation
            interp_text = INTERP.get(top_ctx, f'producing a vocalization associated with {top_ctx}')
            report['interpretation'] = {
                'context': top_ctx,
                'confidence': round(top_prob * 100, 1),
                'description': f'The elephant appears to be {interp_text}.',
                'valence': val_pred,
                'valence_label': {
                    'positive': 'Positive emotional state',
                    'negative': 'Negative or stressed emotional state',
                    'neutral': 'Neutral emotional state',
                }.get(val_pred, val_pred),
                'arousal': aro_pred,
                'arousal_label': {
                    'high': 'High arousal — urgent or intense',
                    'medium': 'Moderate arousal',
                    'low': 'Low arousal — calm or relaxed',
                }.get(aro_pred, aro_pred),
            }

            # Alternative reading
            if len(sorted_idx) > 1:
                alt_ctx = ctx_labels[sorted_idx[1]]
                alt_prob = float(ctx_probs[sorted_idx[1]])
                alt_text = INTERP.get(alt_ctx, f'associated with {alt_ctx}')
                report['interpretation']['alternative'] = {
                    'context': alt_ctx,
                    'confidence': round(alt_prob * 100, 1),
                    'description': f'Alternatively, the elephant may be {alt_text}.',
                }
        else:
            report['interpretation'] = {
                'context': 'Unknown',
                'confidence': 0,
                'description': 'No trained models found. Run the pipeline first to enable inference.',
            }

        return jsonify(report)

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        try:
            os.unlink(tmp_path)
        except:
            pass


if __name__ == '__main__':
    app.run(port=5001, debug=True)
