"""Stage 4: Random Forest classifiers for behavioral context, valence, and arousal."""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.metrics import classification_report, confusion_matrix

VALENCE_MAP = {
    'Affiliative': 'positive', 'Coalition Building': 'positive',
    'Courtship': 'positive', 'Calf Reassurance & Protection': 'positive',
    'Lone & Object Play': 'positive', 'Calf Nourishment & Weaning': 'positive',
    'Aggressive': 'negative', 'Conflict & Confrontation': 'negative',
    'Protest & Distress': 'negative', 'Attacking & Mobbing': 'negative',
    'Avoidance': 'negative', 'Death': 'negative',
    'Foraging & Comfort Technique': 'neutral', 'Maintenance': 'neutral',
    'Attentive': 'neutral', 'Ambivalent': 'neutral',
    'Advertisement & Attraction': 'neutral', 'Birth': 'neutral',
}

AROUSAL_MAP = {
    'Aggressive': 'high', 'Attacking & Mobbing': 'high',
    'Birth': 'high', 'Death': 'high', 'Protest & Distress': 'high',
    'Conflict & Confrontation': 'high', 'Advertisement & Attraction': 'high',
    'Affiliative': 'low', 'Foraging & Comfort Technique': 'low',
    'Maintenance': 'low', 'Lone & Object Play': 'low',
    'Attentive': 'low', 'Ambivalent': 'low',
    'Coalition Building': 'medium', 'Courtship': 'medium',
    'Calf Reassurance & Protection': 'medium', 'Calf Nourishment & Weaning': 'medium',
    'Avoidance': 'medium',
}


def train_classifiers(X_scaled: np.ndarray, metadata: pd.DataFrame, feature_names: list):
    """Train context, valence, and arousal classifiers.

    Returns: context_clf, valence_clf, arousal_clf, cv_scores dict
    """
    contexts = metadata['context'].values
    valence  = [VALENCE_MAP.get(c, 'neutral') for c in contexts]
    arousal  = [AROUSAL_MAP.get(c, 'medium')  for c in contexts]

    X_tr, X_te, y_tr, y_te = train_test_split(
        X_scaled, contexts, test_size=0.2, random_state=42, stratify=contexts
    )

    def _rf():
        return RandomForestClassifier(n_estimators=200, random_state=42, class_weight='balanced')

    context_clf = _rf()
    context_clf.fit(X_tr, y_tr)

    valence_clf = _rf()
    valence_clf.fit(X_scaled, valence)

    arousal_clf = _rf()
    arousal_clf.fit(X_scaled, arousal)

    cv = cross_val_score(context_clf, X_scaled, contexts, cv=5)
    print(f"Context CV accuracy: {cv.mean():.3f} ± {cv.std():.3f}")

    print(classification_report(y_te, context_clf.predict(X_te)))

    return context_clf, valence_clf, arousal_clf, {'context_cv_mean': cv.mean(), 'context_cv_std': cv.std()}


def feature_importances(clf, feature_names: list, top_n: int = 10) -> list:
    """Return top-n (feature, importance) pairs sorted descending."""
    pairs = sorted(zip(feature_names, clf.feature_importances_), key=lambda x: -x[1])
    return pairs[:top_n]


def get_confusion_matrix(context_clf, X_test, y_test, labels):
    return confusion_matrix(y_test, context_clf.predict(X_test), labels=labels)
