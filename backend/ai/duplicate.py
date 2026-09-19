import math
import re
from dataclasses import dataclass, field
from typing import Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from ..config import DUPLICATE_SIMILARITY_THRESHOLD

EARTH_RADIUS_M = 6371000
NEARBY_RADIUS_M = 250
CIVIC_SYNONYMS = {
    "pothole": ["pothole", "potholes", "crater", "pit", "hole", "holes", "sinkhole", "cavity"],
    "garbage": ["garbage", "trash", "waste", "litter", "rubbish", "dump", "dumping"],
    "streetlight": ["streetlight", "streetlights", "lamp", "lamppost", "light", "lighting", "bulb"],
    "drain": ["drain", "drainage", "sewage", "sewer", "gutter", "culvert"],
    "flood": ["flooding", "flooded", "waterlogging", "overflow", "overflowing", "stagnant"],
    "broken": ["broken", "damaged", "cracked", "collapsed", "collapsing", "fallen", "falling"],
    "road": ["road", "street", "lane", "pathway"],
    "footpath": ["footpath", "pavement", "sidewalk"],
    "danger": ["dangerous", "risky", "unsafe", "hazard", "hazardous"],
    "water": ["water", "supply"],
    "leak": ["leak", "leaking", "leakage", "burst"],
}
_SYN = {variant: canonical for canonical, variants in CIVIC_SYNONYMS.items() for variant in variants}
TEXT_WEIGHT = 0.62
LOCATION_WEIGHT = 0.38


@dataclass
class DuplicateMatch:
    complaint_id: int
    complaint_code: str
    civic_issue_id: Optional[int]
    similarity: float
    shared_terms: list = field(default_factory=list)


@dataclass
class DuplicateResult:
    is_duplicate: bool
    best_match: Optional[DuplicateMatch] = None
    all_matches: list = field(default_factory=list)


def _normalize_for_similarity(text: str) -> str:
    tokens = re.findall(r"[a-zA-Z']+", text.lower())
    return " ".join(_SYN.get(tok, tok) for tok in tokens)


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def _shared_terms(text_a: str, text_b: str, top_n: int = 5) -> list:
    words_a = set(re.findall(r"[a-zA-Z']{3,}", text_a.lower()))
    words_b = set(re.findall(r"[a-zA-Z']{3,}", text_b.lower()))
    stop = {"the", "and", "near", "outside", "has", "have", "this", "that", "with", "for"}
    return sorted((words_a & words_b) - stop)[:top_n]


def find_duplicates(new_text: str, new_category: str, new_lat: Optional[float], new_lon: Optional[float], candidates: list) -> DuplicateResult:
    if not candidates:
        return DuplicateResult(is_duplicate=False)
    same_category = [c for c in candidates if c["category"] == new_category]
    if not same_category:
        return DuplicateResult(is_duplicate=False)
    spatially_gated = []
    for c in same_category:
        if new_lat is not None and new_lon is not None and c["latitude"] is not None and c["longitude"] is not None:
            dist = _haversine_m(new_lat, new_lon, c["latitude"], c["longitude"])
            if dist <= NEARBY_RADIUS_M:
                spatially_gated.append(c)
        else:
            spatially_gated.append(c)
    if not spatially_gated:
        return DuplicateResult(is_duplicate=False)
    texts = [_normalize_for_similarity(c["raw_text"]) for c in spatially_gated]
    texts.append(_normalize_for_similarity(new_text))
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1)
    tfidf = vectorizer.fit_transform(texts)
    text_sims = cosine_similarity(tfidf[-1], tfidf[:-1])[0]
    matches = []
    for candidate, text_sim in zip(spatially_gated, text_sims):
        location_bonus = 0.0
        if new_lat is not None and new_lon is not None and candidate["latitude"] is not None and candidate["longitude"] is not None:
            dist = _haversine_m(new_lat, new_lon, candidate["latitude"], candidate["longitude"])
            location_bonus = max(0.0, 1 - (dist / NEARBY_RADIUS_M))
        combined = (TEXT_WEIGHT * text_sim) + (LOCATION_WEIGHT * location_bonus)
        matches.append(DuplicateMatch(
            complaint_id=candidate["id"],
            complaint_code=candidate["complaint_code"],
            civic_issue_id=candidate.get("civic_issue_id"),
            similarity=round(float(combined), 4),
            shared_terms=_shared_terms(new_text, candidate["raw_text"]),
        ))
    matches.sort(key=lambda m: m.similarity, reverse=True)
    best = matches[0]
    is_dup = best.similarity >= DUPLICATE_SIMILARITY_THRESHOLD
    return DuplicateResult(is_duplicate=is_dup, best_match=best if is_dup else None, all_matches=[m for m in matches if m.similarity >= 0.15])
