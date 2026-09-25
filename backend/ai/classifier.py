import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB

from .training_data import TRAINING_EXAMPLES

STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "near", "outside",
    "at", "in", "on", "of", "to", "and", "our", "this", "that", "it",
    "has", "have", "been", "for", "since", "again", "please", "there",
    "with", "very", "still", "not", "we", "i", "my", "me", "us", "will",
    "be",
}

SEVERITY_LEXICON = {
    "huge": 2,
    "large": 1,
    "deep": 1,
    "severe": 2,
    "dangerous": 2,
    "urgent": 2,
    "risky": 1,
    "accident": 2,
    "collapsed": 2,
    "collapse": 2,
    "burst": 2,
    "flooding": 2,
    "flooded": 2,
    "sparking": 2,
    "hazard": 2,
    "unsafe": 1,
    "leaning": 1,
    "cracked": 1,
    "broken": 1,
    "overflowing": 1,
    "school": 1,
    "hospital": 2,
    "children": 2,
    "night": 1,
    "blocked": 1,
    "smell": 1,
    "sewage": 1,
    "small": -1,
    "minor": -1,
}

HISTORICAL_STATS_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "nyc311_historical_stats.json"
)


def _load_historical_stats() -> dict:
    try:
        import json

        with HISTORICAL_STATS_PATH.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError, TypeError):
        return {}


@dataclass
class ClassificationResult:
    category: str
    confidence: float
    all_scores: dict = field(default_factory=dict)
    key_terms: list = field(default_factory=list)
    severity_hint: int = 2


class ComplaintClassifier:
    def __init__(self):
        texts = [text for text, _ in TRAINING_EXAMPLES]
        labels = [category for _, category in TRAINING_EXAMPLES]

        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            min_df=1,
            stop_words="english",
        )
        x = self.vectorizer.fit_transform(texts)

        self.model = MultinomialNB(alpha=0.35)
        self.model.fit(x, labels)
        self.classes_ = self.model.classes_
        self.feature_names = np.array(
            self.vectorizer.get_feature_names_out()
        )
        self.historical_stats = _load_historical_stats()

    def _key_terms(
        self,
        text: str,
        predicted_idx: int,
        top_n: int = 5,
    ) -> list:
        tokens = re.findall(r"[a-zA-Z']+", text.lower())
        tokens = [
            token
            for token in tokens
            if token not in STOPWORDS and len(token) > 2
        ]

        vocab_index = {
            word: index
            for index, word in enumerate(self.feature_names)
        }
        log_probs = self.model.feature_log_prob_[predicted_idx]

        scored = []
        seen = set()
        for token in tokens:
            if token in seen:
                continue
            seen.add(token)
            if token in vocab_index:
                scored.append(
                    (
                        token,
                        float(log_probs[vocab_index[token]]),
                    )
                )

        scored.sort(key=lambda item: item[1], reverse=True)
        return [term for term, _ in scored[:top_n]]

    def _severity(self, text: str) -> int:
        words = re.findall(r"[a-zA-Z']+", text.lower())
        score = 2
        for word in words:
            score += SEVERITY_LEXICON.get(word, 0)
        return int(max(1, min(5, score)))

    def classify(self, text: str) -> ClassificationResult:
        x = self.vectorizer.transform([text])
        probabilities = self.model.predict_proba(x)[0]
        index = int(np.argmax(probabilities))
        category = self.classes_[index]
        confidence = float(probabilities[index])
        all_scores = {
            category_name: round(float(probability), 4)
            for category_name, probability in zip(
                self.classes_,
                probabilities,
            )
        }

        return ClassificationResult(
            category=category,
            confidence=round(confidence, 4),
            all_scores=all_scores,
            key_terms=self._key_terms(text, index),
            severity_hint=self._severity(text),
        )


classifier = ComplaintClassifier()
