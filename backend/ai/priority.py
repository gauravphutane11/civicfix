from dataclasses import dataclass, field
from datetime import datetime, timezone

BANDS = [(80, "CRITICAL"), (60, "HIGH"), (35, "MEDIUM"), (0, "LOW")]
HIGH_IMPACT_CATEGORIES = {"drainage", "pothole", "water_supply"}

@dataclass
class PriorityFactor:
    key: str
    label: str
    points: int
    max_points: int
    explanation: str

@dataclass
class PriorityResult:
    total: int
    band: str
    factors: list = field(default_factory=list)
    def as_list(self):
        return [{"key": f.key, "label": f.label, "points": f.points, "max_points": f.max_points, "explanation": f.explanation} for f in self.factors]

def _band_for(score: int) -> str:
    for threshold, band in BANDS:
        if score >= threshold:
            return band
    return "LOW"

def _ensure_aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

def compute_priority(*, severity_hint: int, complaint_count: int, location_importance: int, created_at: datetime, category: str, has_verified_image_evidence: bool = False) -> PriorityResult:
    factors = []
    severity_points = round((severity_hint / 5) * 30)
    factors.append(PriorityFactor("severity", "Reported severity", severity_points, 30, f'Complaint language scored {severity_hint}/5 on severity cues (e.g. "huge", "dangerous", "blocked").'))
    dup_points = min(25, max(0, (complaint_count - 1)) * 8)
    factors.append(PriorityFactor("recurrence", "Duplicate reports", dup_points, 25, f"{complaint_count} citizen report(s) merged into this issue via similarity matching." if complaint_count > 1 else "Single report so far -- no corroborating duplicates yet."))
    loc_points = min(20, location_importance)
    factors.append(PriorityFactor("location", "Location importance", loc_points, 20, f"Location carries a civic importance weight of {location_importance}/20 (proximity to gates, transit, schools, or main roads)." if location_importance else "Location could not be confidently resolved, so no importance bonus applied."))
    age_hours = max(0, (datetime.now(timezone.utc) - _ensure_aware(created_at)).total_seconds() / 3600)
    age_points = min(15, round((min(age_hours, 72) / 72) * 15))
    factors.append(PriorityFactor("age", "Time unresolved", age_points, 15, f"Open for {age_hours:.1f} hours without resolution."))
    impact_points = 0
    reasons = []
    if category in HIGH_IMPACT_CATEGORIES:
        impact_points += 6
        reasons.append(f'"{category}" issues typically affect many residents at once')
    if has_verified_image_evidence:
        impact_points += 4
        reasons.append("supported by verified photo evidence")
    impact_points = min(10, impact_points)
    factors.append(PriorityFactor("public_impact", "Public impact bonus", impact_points, 10, "; ".join(reasons) if reasons else "No additional impact signals detected."))
    total = min(100, sum(f.points for f in factors))
    return PriorityResult(total=total, band=_band_for(total), factors=factors)
