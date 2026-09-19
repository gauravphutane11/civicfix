import re
from dataclasses import dataclass, field
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from .training_data import TRAINING_EXAMPLES

STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "near", "outside", "at", "in", "on", "of", "to", "and", "our", "this", "that", "it", "has", "have", "been", "for", "since", "again", "please", "there", "with", "very", "still", "not", "we", "i", "my", "me", "us", "will", "be",
}
SEVERITY_LEXICON = {
    "huge": 2, "large": 1, "deep": 1, "severe": 2, "dangerous": 2,
    "urgent": 2, "risky": 1, "accident": 2, "collapsed": 2, "collapse": 2,
    "burst": 2, "flooding": 2, "flooded": 2, "sparking": 2, "hazard": 2,
    "unsafe": 1, "leaning": 1, "cracked": 1, "broken": 1, "overflowing": 1,
    "school": 1, "hospital": 2, "children": 2, "night": 1, "blocked": 1,
    "smell": 1, "sewage": 1, "small": -1, "minor": -1,
}


@dataclass
class ClassificationResult:
    category: str
    confidence: float
    all_scores: dict = field(default_factory=dict)
    key_terms: list = field(default_factory=list)
    severity_hint: int = 2


class ComplaintClassifier:
    def __init__(self):
        texts = [t for t, _ in TRAINING_EXAMPLES]
        labels = [c for _, c in TRAINING_EXAMPLES]
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, stop_words="english")
        X = self.vectorizer.fit_transform(texts)
        self.model = MultinomialNB(alpha=0.35)
        self.model.fit(X, labels)
        self.classes_ = self.model.classes_
        self.feature_names = np.array(self.vectorizer.get_feature_names_out())

    def _key_terms(self, text: str, predicted_idx: int, top_n: int = 5) -> list:
        tokens = re.findall(r"[a-zA-Z']+", text.lower())
        tokens = [t for t in tokens if t not in STOPWORDS and len(t) > 2]
        vocab_index = {w: i for i, w in enumerate(self.feature_names)}
        log_probs = self.model.feature_log_prob_[predicted_idx]
        scored = []
        seen = set()
        for tok in tokens:
            if tok in seen:
                continue
            seen.add(tok)
            if tok in vocab_index:
                scored.append((tok, float(log_probs[vocab_index[tok]])))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [t for t, _ in scored[:top_n]]

    def _severity(self, text: str) -> int:
        words = re.findall(r"[a-zA-Z']+", text.lower())
        score = 2
        for w in words:
            score += SEVERITY_LEXICON.get(w, 0)
        return int(max(1, min(5, score)))

    def classify(self, text: str) -> ClassificationResult:
        X = self.vectorizer.transform([text])
        proba = self.model.predict_proba(X)[0]
        idx = int(np.argmax(proba))
        category = self.classes_[idx]
        confidence = float(proba[idx])
        all_scores = {c: round(float(p), 4) for c, p in zip(self.classes_, proba)}
        return ClassificationResult(
            category=category,
            confidence=round(confidence, 4),
            all_scores=all_scores,
            key_terms=self._key_terms(text, idx),
            severity_hint=self._severity(text),
        )


classifier = ComplaintClassifier()
