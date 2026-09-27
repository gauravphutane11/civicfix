from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB

from .multilingual import (
    LANGUAGE_NAMES,
    MULTILINGUAL_TRAINING_EXAMPLES,
    detect_language,
    key_civic_terms,
    normalize_to_english,
    severity_hint,
)
from .training_data import TRAINING_EXAMPLES

STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "near", "outside",
    "at", "in", "on", "of", "to", "and", "our", "this", "that", "it",
    "has", "have", "been", "for", "since", "again", "please", "there",
    "with", "very", "still", "not", "we", "i", "my", "me", "us", "will",
    "be",
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
    language_code: str = "en"
    language_name: str = "English"
    language_confidence: float = 0.0
    normalized_text: str = ""
    classification_method: str = "multilingual-hybrid"


class ComplaintClassifier:
    def __init__(self):
        english_texts = [text for text, _ in TRAINING_EXAMPLES]
        english_labels = [category for _, category in TRAINING_EXAMPLES]

        # Existing English model remains intact for English complaints.
        self.english_vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            min_df=1,
            stop_words="english",
        )
        english_x = self.english_vectorizer.fit_transform(english_texts)
        self.english_model = MultinomialNB(alpha=0.35)
        self.english_model.fit(english_x, english_labels)

        # Character n-grams work directly on native scripts and are much less
        # brittle than an English word vocabulary when the complaint is Marathi,
        # Hindi, Gujarati, etc. Canonical civic tags are appended during training
        # and inference by normalize_to_english().
        multilingual_texts = [
            normalize_to_english(text, language=None)
            for text, _ in MULTILINGUAL_TRAINING_EXAMPLES
        ]
        multilingual_labels = [category for _, category in MULTILINGUAL_TRAINING_EXAMPLES]
        self.multilingual_vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(2, 5),
            min_df=1,
            sublinear_tf=True,
        )
        multilingual_x = self.multilingual_vectorizer.fit_transform(multilingual_texts)
        self.multilingual_model = MultinomialNB(alpha=0.18)
        self.multilingual_model.fit(multilingual_x, multilingual_labels)

        self.classes_ = np.array(sorted(set(english_labels + multilingual_labels)))
        self.historical_stats = _load_historical_stats()

    def _align_scores(self, classes, probabilities) -> np.ndarray:
        result = np.zeros(len(self.classes_), dtype=float)
        index = {str(name): i for i, name in enumerate(self.classes_)}
        for label, probability in zip(classes, probabilities):
            result[index[str(label)]] = float(probability)
        return result

    def _english_scores(self, text: str) -> np.ndarray:
        x = self.english_vectorizer.transform([text])
        probabilities = self.english_model.predict_proba(x)[0]
        return self._align_scores(self.english_model.classes_, probabilities)

    def _multilingual_scores(self, normalized_text: str) -> np.ndarray:
        x = self.multilingual_vectorizer.transform([normalized_text])
        probabilities = self.multilingual_model.predict_proba(x)[0]
        return self._align_scores(self.multilingual_model.classes_, probabilities)

    @staticmethod
    def _lexicon_scores(text: str, language: str) -> np.ndarray:
        from .multilingual import canonical_terms

        raw = canonical_terms(text, language)
        labels = list(sorted({category for _, category in MULTILINGUAL_TRAINING_EXAMPLES} | {category for _, category in TRAINING_EXAMPLES}))
        scores = np.zeros(len(labels), dtype=float)
        if raw:
            total = float(sum(raw.values()))
            for index, label in enumerate(labels):
                scores[index] = raw.get(label, 0) / total
        return np.array([scores[labels.index(label)] for label in sorted(labels)], dtype=float)

    def _key_terms(self, text: str, normalized_text: str, category: str, language: str, top_n: int = 5) -> list:
        terms = key_civic_terms(text, language, top_n=top_n)
        if terms:
            return terms

        tokens = re.findall(r"[a-zA-Z']+", normalized_text.lower())
        tokens = [token for token in tokens if token not in STOPWORDS and len(token) > 2]
        return list(dict.fromkeys(tokens))[:top_n]

    def classify(self, text: str, language_hint: str | None = None) -> ClassificationResult:
        cleaned = (text or "").strip()
        detection = detect_language(cleaned, language_hint)
        normalized = normalize_to_english(cleaned, detection.code)

        english_scores = self._english_scores(cleaned)
        multilingual_scores = self._multilingual_scores(normalized)

        # Native-script or explicitly selected regional-language complaints rely
        # primarily on the multilingual model. English still contributes a small
        # calibration signal for code-switching such as "रस्त्यावर big pothole".
        is_english = detection.code == "en"
        english_weight = 0.58 if is_english else 0.18
        multilingual_weight = 1.0 - english_weight
        combined = (english_scores * english_weight) + (multilingual_scores * multilingual_weight)

        lexicon = self._lexicon_scores(cleaned, detection.code)
        if np.any(lexicon):
            combined = (combined * 0.72) + (lexicon * 0.28)

        combined_sum = float(combined.sum())
        if combined_sum <= 0:
            combined = np.ones(len(self.classes_), dtype=float) / len(self.classes_)
        else:
            combined = combined / combined_sum

        index = int(np.argmax(combined))
        category = str(self.classes_[index])
        confidence = float(combined[index])
        all_scores = {
            str(category_name): round(float(probability), 4)
            for category_name, probability in zip(self.classes_, combined)
        }

        direct_terms = key_civic_terms(cleaned, detection.code, top_n=5)
        method = "multilingual-hybrid"
        if is_english:
            method = "english-model + multilingual-calibration"
        elif direct_terms:
            method = "language-detected + multilingual-model + civic-vocabulary"

        return ClassificationResult(
            category=category,
            confidence=round(confidence, 4),
            all_scores=all_scores,
            key_terms=self._key_terms(cleaned, normalized, category, detection.code),
            severity_hint=severity_hint(cleaned, detection.code),
            language_code=detection.code,
            language_name=LANGUAGE_NAMES.get(detection.code, detection.name),
            language_confidence=detection.confidence,
            normalized_text=normalized,
            classification_method=method,
        )


classifier = ComplaintClassifier()
