import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Optional

from ..data.gazetteer import GAZETTEER

LOCATION_PATTERNS = [
    r"(?:near|outside|behind|at|beside|opposite|in front of|next to|around|by)\s+(?:the\s+)?([a-zA-Z0-9'\s]{3,60}?)(?:[.,;!]|$|\s+is\s+|\s+has\s+|\s+with\s+|\s+and\s+|\s+which\s+|\s+that\s+|\s+causing\s+|\s+because\s+|\s+for\s+|\s+since\s+|\s+where\s+)",
]

MATCH_THRESHOLD = 0.72

GENERIC_LOCATION_WORDS = {
    "area",
    "bridge",
    "crossing",
    "flyover",
    "gate",
    "junction",
    "lane",
    "location",
    "main",
    "park",
    "parking",
    "place",
    "road",
    "roundabout",
    "sidewalk",
    "signal",
    "site",
    "station",
    "street",
    "the road",
    "the street",
    "the lane",
    "the area",
    "the sidewalk",
}

GENERIC_PHRASES = {
    "the road",
    "road",
    "the street",
    "street",
    "the lane",
    "lane",
    "the area",
    "area",
    "the sidewalk",
    "sidewalk",
    "the junction",
    "junction",
    "the crossing",
    "crossing",
    "the bridge",
    "bridge",
    "the park",
    "park",
}


@dataclass
class LocationResult:
    matched: bool
    place_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    confidence: float = 0.0
    raw_phrase: Optional[str] = None
    importance_weight: int = 8
    area_type: Optional[str] = None
    candidates: list = field(default_factory=list)


def _normalize_phrase(phrase: str) -> str:
    return re.sub(r"\s+", " ", phrase.strip().lower())


def _is_generic_phrase(phrase: str) -> bool:
    normalized = _normalize_phrase(phrase)
    if normalized in GENERIC_PHRASES:
        return True

    tokens = normalized.split()
    if len(tokens) <= 2 and all(token in GENERIC_LOCATION_WORDS for token in tokens):
        return True

    return False


def _extract_phrases(text: str) -> list:
    phrases = []
    lower = text.lower()

    for pattern in LOCATION_PATTERNS:
        for match in re.finditer(pattern, lower):
            phrase = _normalize_phrase(match.group(1))
            if phrase and not _is_generic_phrase(phrase):
                phrases.append(phrase)

    return phrases


def _alias_score(phrase: str, alias: str) -> float:
    phrase = _normalize_phrase(phrase)
    alias = _normalize_phrase(alias)

    if phrase == alias:
        return 1.0

    if len(alias) >= 6:
        alias_pattern = rf"\b{re.escape(alias)}\b"
        if re.search(alias_pattern, phrase):
            return 0.92

    return SequenceMatcher(None, phrase, alias).ratio()


def _best_gazetteer_match(phrase: str):
    best = None
    best_score = 0.0

    for entry in GAZETTEER:
        aliases = [
            entry["name"].lower(),
            *entry.get("aliases", []),
        ]

        for alias in aliases:
            score = _alias_score(phrase, alias)
            if score > best_score:
                best_score = score
                best = entry

    return best, best_score


def _fallback_exact_alias(text: str):
    matches = []
    for entry in GAZETTEER:
        aliases = [
            entry["name"].lower(),
            *entry.get("aliases", []),
        ]

        for alias in aliases:
            alias = _normalize_phrase(alias)
            if len(alias) < 5 or _is_generic_phrase(alias):
                continue

            pattern = rf"\b{re.escape(alias)}\b"
            if re.search(pattern, text.lower()):
                matches.append((len(alias), entry, alias))

    if not matches:
        return None

    _, entry, alias = max(matches, key=lambda item: item[0])
    return entry, alias


def extract_location(text: str) -> LocationResult:
    phrases = _extract_phrases(text)

    best_overall = None
    best_overall_score = 0.0
    best_phrase = None
    candidates = []

    for phrase in phrases:
        entry, score = _best_gazetteer_match(phrase)
        if entry:
            candidates.append(
                {
                    "phrase": phrase,
                    "place": entry["name"],
                    "score": round(score, 3),
                }
            )

        if entry and score > best_overall_score:
            best_overall = entry
            best_overall_score = score
            best_phrase = phrase

    if not best_overall or best_overall_score < MATCH_THRESHOLD:
        fallback = _fallback_exact_alias(text)
        if fallback:
            entry, alias = fallback
            best_overall = entry
            best_overall_score = 0.86
            best_phrase = alias
            candidates.append(
                {
                    "phrase": alias,
                    "place": entry["name"],
                    "score": best_overall_score,
                }
            )

    if best_overall and best_overall_score >= MATCH_THRESHOLD:
        return LocationResult(
            matched=True,
            place_name=best_overall["name"],
            latitude=best_overall["latitude"],
            longitude=best_overall["longitude"],
            confidence=round(best_overall_score, 3),
            raw_phrase=best_phrase,
            importance_weight=best_overall["importance_weight"],
            area_type=best_overall["area_type"],
            candidates=candidates,
        )

    return LocationResult(
        matched=False,
        raw_phrase=phrases[0] if phrases else None,
        candidates=candidates,
    )
