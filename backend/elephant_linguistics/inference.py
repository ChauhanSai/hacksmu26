"""Stage 5: Meaning vector construction and human-readable interpretation."""

import numpy as np
import pandas as pd

INTERPRETATION_TEMPLATES = {
    'Affiliative': {
        'base': "The elephant is engaging in social bonding or friendly contact",
        'modifiers': {
            'calf': "— likely a calf seeking comfort from a family member",
            'adult_female': "— consistent with a matriarch maintaining social bonds",
            'high_arousal': " with notable enthusiasm",
            'low_arousal': " in a calm, relaxed manner",
            'directed': " and appears to be addressing {target} specifically",
            'trunk_extended': " while extending its trunk (tactile greeting)",
        },
    },
    'Aggressive': {
        'base': "The elephant is displaying aggressive or threatening behavior",
        'modifiers': {
            'adult_male': "— likely a dominance assertion",
            'high_arousal': " with high intensity, possibly escalating to confrontation",
            'directed': " directed at {target}",
            'ears_spread': " with ears spread wide (visual threat display)",
        },
    },
    'Protest & Distress': {
        'base': "The elephant appears to be in distress or protesting a situation",
        'modifiers': {
            'calf': "— the calf may be separated from its mother or uncomfortable",
            'high_arousal': " with high urgency",
            'low_arousal': " at a low level, possibly mild discomfort",
        },
    },
    'Calf Reassurance & Protection': {
        'base': "An adult is providing reassurance or protection to a calf",
        'modifiers': {
            'adult_female': "— likely the mother responding to calf distress",
            'trunk_extended': " using trunk contact for physical comfort",
        },
    },
    'Calf Nourishment & Weaning': {
        'base': "The call is associated with nursing or feeding of a calf",
        'modifiers': {
            'calf': "— the calf may be requesting to nurse",
            'adult_female': "— the mother may be signaling feeding time or beginning weaning",
        },
    },
    'Foraging & Comfort Technique': {
        'base': "The elephant is likely signaling interest in food or foraging activity",
        'modifiers': {
            'high_arousal': " — may have located a food source and is alerting others",
            'low_arousal': " in a routine manner",
        },
    },
    'Courtship': {
        'base': "The call is associated with courtship or mating behavior",
        'modifiers': {
            'adult_male': "— likely a male advertising reproductive fitness",
            'adult_female': "— the female may be signaling receptivity",
        },
    },
    'Advertisement & Attraction': {
        'base': "The elephant is producing an advertisement call to attract attention",
        'modifiers': {
            'adult_male': "— possibly a musth rumble signaling dominance and reproductive state",
        },
    },
    'Coalition Building': {
        'base': "The elephant is coordinating with others, building alliances or group cohesion",
        'modifiers': {
            'adult_female': "— consistent with a matriarch organizing group activity",
        },
    },
    'Conflict & Confrontation': {
        'base': "The call is associated with an active conflict or confrontation",
        'modifiers': {'high_arousal': " with high intensity"},
    },
    'Attacking & Mobbing': {
        'base': "The elephant is involved in an attack or group mobbing behavior",
        'modifiers': {'high_arousal': " — the situation appears highly escalated"},
    },
    'Attentive': {
        'base': "The elephant is in an alert, attentive state — listening or monitoring",
        'modifiers': {'ears_spread': " with ears extended for acoustic scanning"},
    },
    'Avoidance': {
        'base': "The elephant is signaling avoidance or retreat",
        'modifiers': {
            'calf': "— a calf may be attempting to avoid an unpleasant interaction",
            'high_arousal': " with urgency, possibly fleeing",
        },
    },
    'Ambivalent': {
        'base': "The call is ambiguous — the elephant may be in a mixed or uncertain emotional state",
        'modifiers': {},
    },
    'Birth': {
        'base': "The call is associated with a birth event",
        'modifiers': {
            'adult_female': "— the mother or attending females are vocalizing during or after birth",
        },
    },
    'Death': {
        'base': "The call is associated with a death event — possibly mourning or distress",
        'modifiers': {'high_arousal': " with intense emotional expression"},
    },
    'Lone & Object Play': {
        'base': "The elephant is vocalizing during solitary play or interaction with objects",
        'modifiers': {'calf': "— a calf playing on its own, vocalizations may be self-directed"},
    },
    'Maintenance': {
        'base': "The call is associated with routine maintenance behavior (resting, dust bathing, drinking)",
        'modifiers': {},
    },
}


def build_meaning_vector(feature_vector_scaled: np.ndarray, metadata_row,
                          context_clf, valence_clf, arousal_clf, gmm,
                          name_candidates=None) -> dict:
    fv = feature_vector_scaled.reshape(1, -1)

    ctx_probs  = context_clf.predict_proba(fv)[0]
    ctx_labels = context_clf.classes_
    sorted_ctx = np.argsort(ctx_probs)[::-1]

    val_probs = valence_clf.predict_proba(fv)[0]
    aro_probs = arousal_clf.predict_proba(fv)[0]

    symbol       = int(gmm.predict(fv)[0])
    cluster_prob = float(np.max(gmm.predict_proba(fv)[0]))

    directed_at = None
    if name_candidates is not None and not name_candidates.empty:
        caller = metadata_row.get('elephant_id')
        if caller:
            match = name_candidates[
                (name_candidates['caller'] == caller) &
                (name_candidates['symbol'] == symbol)
            ]
            if len(match) > 0:
                directed_at = match.iloc[0]['directed_at']

    return {
        'symbol':              symbol,
        'cluster_confidence':  cluster_prob,
        'top_context':         ctx_labels[sorted_ctx[0]],
        'context_confidence':  float(ctx_probs[sorted_ctx[0]]),
        'alt_context':         ctx_labels[sorted_ctx[1]],
        'alt_confidence':      float(ctx_probs[sorted_ctx[1]]),
        'valence':             valence_clf.classes_[np.argmax(val_probs)],
        'arousal':             arousal_clf.classes_[np.argmax(aro_probs)],
        'caller_age_sex':      metadata_row.get('age_sex', 'unknown'),
        'body_part':           metadata_row.get('body_part', 'unknown'),
        'comm_mode':           metadata_row.get('comm_mode', 'unknown'),
        'directed_at':         directed_at,
        'context_probabilities': dict(zip(ctx_labels, ctx_probs.tolist())),
    }


def generate_interpretation(mv: dict) -> dict:
    ctx      = mv['top_context']
    template = INTERPRETATION_TEMPLATES.get(ctx, {'base': f"The call is associated with {ctx}", 'modifiers': {}})
    mods     = template['modifiers']
    sentence = template['base']

    age_sex   = str(mv.get('caller_age_sex', '')).lower()
    arousal   = mv.get('arousal', '')
    body_part = str(mv.get('body_part', '')).lower()
    directed  = mv.get('directed_at')

    if 'calf' in age_sex and 'calf' in mods:
        sentence += mods['calf']
    elif 'adult' in age_sex and 'female' in age_sex and 'adult_female' in mods:
        sentence += mods['adult_female']
    elif 'adult' in age_sex and 'male' in age_sex and 'adult_male' in mods:
        sentence += mods['adult_male']

    arousal_key = f"{arousal}_arousal"
    if arousal_key in mods:
        sentence += mods[arousal_key]

    if 'trunk' in body_part and 'trunk_extended' in mods:
        sentence += mods['trunk_extended']
    if 'ear' in body_part and 'ears_spread' in mods:
        sentence += mods['ears_spread']

    if directed and 'directed' in mods:
        sentence += mods['directed'].format(target=directed)

    if not sentence.endswith('.'):
        sentence += '.'

    confidence = mv['context_confidence'] * 100
    return {
        'interpretation':   sentence,
        'confidence':       f"{confidence:.1f}%",
        'confidence_note':  'acoustic pattern match to previously observed behavioral contexts',
        'alternative':      f"Could also be: {mv['alt_context']} ({mv['alt_confidence'] * 100:.1f}%)",
    }


def process_full_dataset(feature_matrix, metadata, scaler, gmm,
                          context_clf, valence_clf, arousal_clf,
                          name_candidates=None) -> pd.DataFrame:
    X = scaler.transform(feature_matrix)
    results = []
    for i in range(len(feature_matrix)):
        mv     = build_meaning_vector(X[i], metadata.iloc[i], context_clf, valence_clf, arousal_clf, gmm, name_candidates)
        interp = generate_interpretation(mv)
        results.append({
            'call_index': i,
            'filename':   metadata.iloc[i].get('filename', f'call_{i}'),
            **mv,
            **interp,
        })
    return pd.DataFrame(results)


def print_call_report(row: dict, call_idx: int = None):
    sep = '═' * 63
    idx = row.get('call_index', call_idx)
    print(f"\n{sep}")
    print(f"CALL ANALYSIS #{str(idx).zfill(4)}")
    print(sep)
    print(f"Audio:  {row.get('filename', 'unknown')}")
    print(f"Symbol: Cluster {row['symbol']}  (confidence {row['cluster_confidence']:.1%})")
    print(f"Caller: {row.get('caller_age_sex', 'unknown')}")
    print(f"\nINTERPRETATION:")
    print(f'"{row["interpretation"]}"')
    print(f"\nConfidence: {row['confidence']} ({row['confidence_note']})")
    print(f"{row['alternative']}")
    print(f"\nVALENCE: {row['valence'].capitalize()} | AROUSAL: {row['arousal'].capitalize()}")
    print(f"Body Part: {row.get('body_part', 'unknown')} | Mode: {row.get('comm_mode', 'unknown')}")
    top_probs = sorted(row['context_probabilities'].items(), key=lambda x: -x[1])[:5]
    print("\nCONTEXT PROBABILITIES:")
    for ctx, prob in top_probs:
        bar = '.' * max(0, 32 - len(ctx))
        print(f"  {ctx} {bar} {prob * 100:.1f}%")
    print(sep)
