"""Lightweight evidence consistency matching for CivicFix completion photos.

This module is intentionally an evidence *consistency signal*, not a claim of proof.
It combines scene-level visual similarity with geospatial proximity between the field
worker completion photo and a citizen's optional after-work photo.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, radians, sin, sqrt
from pathlib import Path

import cv2
import numpy as np


MAX_VERIFICATION_DISTANCE_METERS = 150.0
VERIFIED_VISUAL_THRESHOLD = 0.30
VERIFIED_COMBINED_THRESHOLD = 0.56
REVIEW_COMBINED_THRESHOLD = 0.36


@dataclass(frozen=True)
class EvidenceMatch:
    visual_similarity: float
    location_distance_meters: float
    location_score: float
    verification_score: float
    status: str
    note: str


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius = 6_371_000.0
    p1 = radians(lat1)
    p2 = radians(lat2)
    dp = radians(lat2 - lat1)
    dl = radians(lon2 - lon1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return earth_radius * 2 * atan2(sqrt(a), sqrt(1 - a))


def _read_image(path: str) -> np.ndarray | None:
    data = np.fromfile(str(Path(path)), dtype=np.uint8)
    if data.size == 0:
        return None
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        return None
    return cv2.resize(image, (640, 480), interpolation=cv2.INTER_AREA)


def _orb_similarity(a: np.ndarray, b: np.ndarray) -> float:
    gray_a = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    gray_b = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    orb = cv2.ORB_create(nfeatures=1200, fastThreshold=12)
    key_a, desc_a = orb.detectAndCompute(gray_a, None)
    key_b, desc_b = orb.detectAndCompute(gray_b, None)
    if desc_a is None or desc_b is None or not key_a or not key_b:
        return 0.0
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    raw_matches = matcher.knnMatch(desc_a, desc_b, k=2)
    good = []
    for pair in raw_matches:
        if len(pair) != 2:
            continue
        first, second = pair
        if first.distance < 0.78 * second.distance:
            good.append(first)
    denom = max(14, min(len(key_a), len(key_b)) * 0.22)
    return float(min(1.0, len(good) / denom))


def _histogram_similarity(a: np.ndarray, b: np.ndarray) -> float:
    hsv_a = cv2.cvtColor(a, cv2.COLOR_BGR2HSV)
    hsv_b = cv2.cvtColor(b, cv2.COLOR_BGR2HSV)
    hist_a = cv2.calcHist([hsv_a], [0, 1], None, [16, 16], [0, 180, 0, 256])
    hist_b = cv2.calcHist([hsv_b], [0, 1], None, [16, 16], [0, 180, 0, 256])
    cv2.normalize(hist_a, hist_a)
    cv2.normalize(hist_b, hist_b)
    correlation = float(cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_CORREL))
    return float(np.clip((correlation + 1.0) / 2.0, 0.0, 1.0))


def _structure_similarity(a: np.ndarray, b: np.ndarray) -> float:
    gray_a = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    gray_b = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    diff = np.mean(np.abs(gray_a - gray_b))
    return float(np.clip(1.0 - diff * 2.2, 0.0, 1.0))


def visual_similarity(worker_path: str, citizen_path: str) -> float:
    worker = _read_image(worker_path)
    citizen = _read_image(citizen_path)
    if worker is None or citizen is None:
        return 0.0
    orb = _orb_similarity(worker, citizen)
    hist = _histogram_similarity(worker, citizen)
    structure = _structure_similarity(worker, citizen)
    score = 0.55 * orb + 0.25 * hist + 0.20 * structure
    return float(np.clip(score, 0.0, 1.0))


def compare_evidence(
    worker_path: str,
    worker_latitude: float,
    worker_longitude: float,
    citizen_path: str,
    citizen_latitude: float,
    citizen_longitude: float,
) -> EvidenceMatch:
    distance = haversine_meters(
        worker_latitude,
        worker_longitude,
        citizen_latitude,
        citizen_longitude,
    )
    location_score = float(
        max(0.0, 1.0 - distance / MAX_VERIFICATION_DISTANCE_METERS)
    )
    visual = visual_similarity(worker_path, citizen_path)
    combined = float(0.70 * visual + 0.30 * location_score)

    if distance <= MAX_VERIFICATION_DISTANCE_METERS and visual >= VERIFIED_VISUAL_THRESHOLD and combined >= VERIFIED_COMBINED_THRESHOLD:
        status = "verified"
        note = (
            "Worker and citizen completion photos show sufficient scene consistency "
            "and were captured within the configured spatial verification radius."
        )
    elif distance <= MAX_VERIFICATION_DISTANCE_METERS and combined >= REVIEW_COMBINED_THRESHOLD:
        status = "needs_review"
        note = (
            "The evidence is geographically close but the visual consistency signal "
            "is not strong enough for automatic verification."
        )
    else:
        status = "needs_review"
        note = (
            "The paired completion evidence did not meet the automatic visual/location "
            "verification threshold and should be checked by an administrator."
        )

    return EvidenceMatch(
        visual_similarity=round(visual, 4),
        location_distance_meters=round(distance, 2),
        location_score=round(location_score, 4),
        verification_score=round(combined, 4),
        status=status,
        note=note,
    )

