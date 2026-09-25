import json
from pathlib import Path

from sqlalchemy.orm import Session

from .. import models, sla_utils
from .classifier import classifier
from .duplicate import find_duplicates
from .location import extract_location
from .priority import compute_priority

HISTORICAL_STATS_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "nyc311_historical_stats.json"
)


def _load_historical_stats() -> dict:
    try:
        with HISTORICAL_STATS_PATH.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError, TypeError):
        return {}


def location_importance_of(issue_or_complaint) -> int:
    location = getattr(issue_or_complaint, "location", None)
    importance = getattr(location, "importance_weight", None)
    if importance:
        return int(importance)

    if (
        getattr(issue_or_complaint, "latitude", None) is not None
        and getattr(issue_or_complaint, "longitude", None) is not None
    ):
        return 8

    return 4


_location_importance = location_importance_of


def _historical_context(category: str) -> dict | None:
    stats = _load_historical_stats()
    if not stats:
        return None

    category_counts = stats.get("category_counts", {})
    category_records = int(category_counts.get(category, 0))
    total_records = int(stats.get("records", 0))
    share = (
        round((category_records / total_records) * 100, 2)
        if total_records
        else 0.0
    )

    top_descriptors = stats.get("top_descriptors", {}).get(category, [])

    return {
        "source": stats.get("source", "NYC 311 Service Requests"),
        "source_period": stats.get("source_period", "2019"),
        "records": total_records,
        "category_records": category_records,
        "category_share_pct": share,
        "top_descriptors": list(top_descriptors)[:5],
    }


def _ai_explanation(
    complaint: models.Complaint,
    issue: models.CivicIssue,
    duplicate_info: dict,
    priority,
) -> str:
    parts = []

    category_confidence = round(
        float(complaint.category_confidence or 0) * 100
    )
    terms = ", ".join(complaint.category_terms or [])

    if complaint.category:
        text = (
            f"AI classified this report as {complaint.category.replace('_', ' ')} "
            f"with {category_confidence}% confidence."
        )
        if terms:
            text += f" Key supporting terms: {terms}."
        parts.append(text)

    if complaint.location_text_raw == "Shared device location":
        parts.append(
            "Device location was captured successfully and used for civic issue "
            "mapping and nearby duplicate detection."
        )
    elif complaint.location_text_raw:
        location_confidence = round(
            float(complaint.location_confidence or 0) * 100
        )
        if complaint.location_confidence:
            parts.append(
                f"Location matched to {complaint.location_text_raw} with "
                f"{location_confidence}% confidence."
            )
        else:
            parts.append(
                f"Location text was recorded as {complaint.location_text_raw}, "
                "but the place could not be confidently resolved."
            )

    if duplicate_info.get("is_duplicate"):
        similarity = float(duplicate_info.get("similarity") or 0) * 100
        parts.append(
            f"A probable duplicate was linked to {duplicate_info.get('matched_complaint_code')} "
            f"at {similarity:.0f}% combined similarity, consolidating the report into the "
            f"same civic issue ({issue.issue_code})."
        )
    else:
        parts.append(
            f"No sufficiently similar nearby report crossed the duplicate threshold, "
            f"so this report opened {issue.issue_code} as a new civic issue."
        )

    parts.append(
        f"Priority is {priority.total}/100 ({priority.band}) using reported severity, "
        "recurrence, location importance, unresolved age and public-impact signals."
    )

    return " ".join(parts)


def run_triage(db: Session, complaint: models.Complaint) -> dict:
    # -----------------------------------------------------
    # 1. CLASSIFY
    # -----------------------------------------------------
    result = classifier.classify(complaint.raw_text)
    complaint.category = result.category
    complaint.category_confidence = result.confidence
    complaint.category_terms = result.key_terms
    complaint.severity_hint = result.severity_hint

    # -----------------------------------------------------
    # 2. LOCATION
    # -----------------------------------------------------
    location_matched = False

    if complaint.latitude is None or complaint.longitude is None:
        location = extract_location(complaint.raw_text)

        if location.matched:
            location_matched = True
            complaint.location_text_raw = location.place_name
            complaint.location_confidence = location.confidence
            complaint.latitude = location.latitude
            complaint.longitude = location.longitude

            gazetteer_location = (
                db.query(models.Location)
                .filter(models.Location.name == location.place_name)
                .first()
            )
            complaint.location_id = (
                gazetteer_location.id
                if gazetteer_location
                else None
            )

        elif location.raw_phrase:
            complaint.location_text_raw = (
                f"{location.raw_phrase} (unresolved)"
            )
            complaint.location_confidence = 0.0
    else:
        complaint.location_text_raw = "Shared device location"
        complaint.location_confidence = 1.0
        location_matched = True

    db.flush()

    # -----------------------------------------------------
    # 3. DUPLICATE DETECTION
    # -----------------------------------------------------
    candidate_rows = (
        db.query(models.Complaint)
        .filter(models.Complaint.id != complaint.id)
        .filter(models.Complaint.category == complaint.category)
        .all()
    )

    candidates = [
        {
            "id": candidate.id,
            "complaint_code": candidate.complaint_code,
            "raw_text": candidate.raw_text,
            "category": candidate.category,
            "latitude": candidate.latitude,
            "longitude": candidate.longitude,
            "civic_issue_id": candidate.civic_issue_id,
        }
        for candidate in candidate_rows
        if candidate.civic_issue_id is not None
    ]

    duplicate_result = find_duplicates(
        complaint.raw_text,
        complaint.category,
        complaint.latitude,
        complaint.longitude,
        candidates,
    )

    duplicate_info = {
        "is_duplicate": False,
        "matched_complaint_code": None,
        "similarity": None,
        "shared_terms": [],
        "civic_issue_code": None,
    }

    if (
        duplicate_result.is_duplicate
        and duplicate_result.best_match
        and duplicate_result.best_match.civic_issue_id
    ):
        issue = db.get(
            models.CivicIssue,
            duplicate_result.best_match.civic_issue_id,
        )

        complaint.civic_issue_id = issue.id
        complaint.status = models.ComplaintStatus.MERGED.value
        issue.complaint_count = (issue.complaint_count or 1) + 1

        db.add(
            models.DuplicateLink(
                civic_issue_id=issue.id,
                complaint_id=complaint.id,
                matched_against_complaint_id=(
                    duplicate_result.best_match.complaint_id
                ),
                similarity=duplicate_result.best_match.similarity,
                reason=(
                    f"TF-IDF cosine similarity "
                    f"{duplicate_result.best_match.similarity:.2f} with "
                    f"{duplicate_result.best_match.complaint_code}; shared terms: "
                    f"{', '.join(duplicate_result.best_match.shared_terms) or 'n/a'}"
                ),
            )
        )

        duplicate_info.update(
            {
                "is_duplicate": True,
                "matched_complaint_code": (
                    duplicate_result.best_match.complaint_code
                ),
                "similarity": duplicate_result.best_match.similarity,
                "shared_terms": duplicate_result.best_match.shared_terms,
                "civic_issue_code": issue.issue_code,
            }
        )
    else:
        issue = models.CivicIssue(
            category=complaint.category,
            representative_text=complaint.raw_text,
            location_id=complaint.location_id,
            location_text_raw=complaint.location_text_raw,
            latitude=complaint.latitude,
            longitude=complaint.longitude,
            complaint_count=1,
            status=models.IssueStatus.OPEN.value,
        )
        db.add(issue)
        db.flush()

        complaint.civic_issue_id = issue.id
        complaint.status = models.ComplaintStatus.TRIAGED.value

        db.add(
            models.StatusHistory(
                civic_issue_id=issue.id,
                from_status=None,
                to_status=models.IssueStatus.OPEN.value,
                changed_by="AI Triage",
                note="Issue opened from citizen report.",
            )
        )
        db.flush()

    # -----------------------------------------------------
    # 4. PRIORITY
    # -----------------------------------------------------
    merged_complaints = (
        db.query(models.Complaint)
        .filter(models.Complaint.civic_issue_id == issue.id)
        .all()
    )

    max_severity = max(
        (item.severity_hint or 2 for item in merged_complaints),
        default=2,
    )

    has_verified_evidence = any(
        attachment.is_verified
        for item in merged_complaints
        for attachment in item.attachments
    )

    priority = compute_priority(
        severity_hint=max_severity,
        complaint_count=issue.complaint_count,
        location_importance=_location_importance(issue),
        created_at=issue.created_at,
        category=issue.category,
        has_verified_image_evidence=has_verified_evidence,
    )

    issue.priority_score = priority.total
    issue.priority_band = priority.band
    issue.priority_breakdown = priority.as_list()

    # -----------------------------------------------------
    # 5. SLA
    # -----------------------------------------------------
    sla_record = sla_utils.upsert_sla(db, issue)
    db.flush()

    # -----------------------------------------------------
    # 6. HISTORICAL CONTEXT + AI EXPLANATION
    # -----------------------------------------------------
    historical_context = _historical_context(complaint.category)
    ai_explanation = _ai_explanation(
        complaint,
        issue,
        duplicate_info,
        priority,
    )

    return {
        "issue": issue,
        "duplicate_info": duplicate_info,
        "location_matched": location_matched,
        "sla_record": sla_record,
        "priority": priority,
        "historical_context": historical_context,
        "ai_explanation": ai_explanation,
    }
