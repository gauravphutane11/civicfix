import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Optional
from ..data.gazetteer import GAZETTEER

LOCATION_PATTERNS = [
    r"(?:near|outside|behind|at|beside|opposite|in front of|next to|around|by)\s+(?:the\s+)?([a-zA-Z0-9'\s]{3,40}?)(?:[.,;!]|$|\s+is\s+|\s+has\s+| and | which | that | causing | because | for | since )",
]
MATCH_THRESHOLD = 0.72


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


def _extract_phrases(text: str) -> list:
    phrases = []
    low = text.lower()
    for pattern in LOCATION_PATTERNS:
        for m in re.finditer(pattern, low):
            phrase = re.sub(r"\s+", " ", m.group(1).strip())
            if phrase:
                phrases.append(phrase)
    return phrases


def _best_gazetteer_match(phrase: str):
    best = None
    best_score = 0.0
    for entry in GAZETTEER:
        for alias in [entry["name"].lower()] + entry["aliases"]:
            score = SequenceMatcher(None, phrase, alias).ratio()
            if phrase in alias or alias in phrase:
                score = max(score, 0.85)
            if score > best_score:
                best_score = score
                best = entry
    return best, best_score


def extract_location(text: str) -> LocationResult:
    phrases = _extract_phrases(text)
    if not phrases:
        return LocationResult(matched=False)
    best_overall = None
    best_overall_score = 0.0
    best_phrase = None
    candidates = []
    for phrase in phrases:
        entry, score = _best_gazetteer_match(phrase)
        if entry:
            candidates.append({"phrase": phrase, "place": entry["name"], "score": round(score, 3)})
        if entry and score > best_overall_score:
            best_overall = entry
            best_overall_score = score
            best_phrase = phrase
    if not best_overall or best_overall_score < MATCH_THRESHOLD:
        full = low
        fallback = []
        for entry in GAZETTEER:
            for alias in [entry["name"].lower()] + entry["aliases"]:
                if len(alias) >= 4 and alias in full:
                    fallback.append((len(alias), entry, alias))
        if fallback:
            _, best_overall, best_alias = max(fallback, key=lambda x: x[0])
            best_overall_score = 0.86
            best_phrase = best_alias
            candidates.append({"phrase": best_alias, "place": best_overall["name"], "score": best_overall_score})

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
    return LocationResult(matched=False, raw_phrase=phrases[0] if phrases else None, candidates=candidates)
