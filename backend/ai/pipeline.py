from sqlalchemy.orm import Session
from .. import models, sla_utils
from .classifier import classifier
from .location import extract_location
from .duplicate import find_duplicates
from .priority import compute_priority


def location_importance_of(issue_or_complaint) -> int:
    if issue_or_complaint.location and issue_or_complaint.location.importance_weight:
        return issue_or_complaint.location.importance_weight
    return 8 if issue_or_complaint.latitude is not None else 4

_location_importance = location_importance_of


def run_triage(db: Session, complaint: models.Complaint) -> dict:
    result = classifier.classify(complaint.raw_text)
    complaint.category = result.category
    complaint.category_confidence = result.confidence
    complaint.category_terms = result.key_terms
    complaint.severity_hint = result.severity_hint

    location_matched = False
    if complaint.latitude is None or complaint.longitude is None:
        loc = extract_location(complaint.raw_text)
        if loc.matched:
            location_matched = True
            complaint.location_text_raw = loc.place_name
            complaint.location_confidence = loc.confidence
            complaint.latitude, complaint.longitude = loc.latitude, loc.longitude
            gazetteer_loc = db.query(models.Location).filter(models.Location.name == loc.place_name).first()
            complaint.location_id = gazetteer_loc.id if gazetteer_loc else None
        elif loc.raw_phrase:
            complaint.location_text_raw = f"{loc.raw_phrase} (unresolved)"
            complaint.location_confidence = 0.0
    else:
        complaint.location_text_raw = "Shared device location"
        complaint.location_confidence = 1.0
        location_matched = True
    db.flush()

    candidate_rows = (
        db.query(models.Complaint)
        .filter(models.Complaint.id != complaint.id)
        .filter(models.Complaint.category == complaint.category)
        .all()
    )
    candidates = [
        {"id": c.id, "complaint_code": c.complaint_code, "raw_text": c.raw_text, "category": c.category,
         "latitude": c.latitude, "longitude": c.longitude, "civic_issue_id": c.civic_issue_id}
        for c in candidate_rows if c.civic_issue_id is not None
    ]
    dup_result = find_duplicates(complaint.raw_text, complaint.category, complaint.latitude, complaint.longitude, candidates)
    duplicate_info = {"is_duplicate": False, "matched_complaint_code": None, "similarity": None, "shared_terms": [], "civic_issue_code": None}

    if dup_result.is_duplicate and dup_result.best_match and dup_result.best_match.civic_issue_id:
        issue = db.get(models.CivicIssue, dup_result.best_match.civic_issue_id)
        complaint.civic_issue_id = issue.id
        complaint.status = models.ComplaintStatus.MERGED.value
        issue.complaint_count = (issue.complaint_count or 1) + 1
        db.add(models.DuplicateLink(
            civic_issue_id=issue.id, complaint_id=complaint.id,
            matched_against_complaint_id=dup_result.best_match.complaint_id,
            similarity=dup_result.best_match.similarity,
            reason=(f"TF-IDF cosine similarity {dup_result.best_match.similarity:.2f} with "
                    f"{dup_result.best_match.complaint_code}; shared terms: "
                    f"{', '.join(dup_result.best_match.shared_terms) or 'n/a'}"),
        ))
        duplicate_info.update({
            "is_duplicate": True,
            "matched_complaint_code": dup_result.best_match.complaint_code,
            "similarity": dup_result.best_match.similarity,
            "shared_terms": dup_result.best_match.shared_terms,
            "civic_issue_code": issue.issue_code,
        })
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
        db.add(models.StatusHistory(
            civic_issue_id=issue.id, from_status=None, to_status=models.IssueStatus.OPEN.value,
            changed_by="AI Triage", note="Issue opened from citizen report.",
        ))
        db.flush()

    merged_complaints = db.query(models.Complaint).filter(models.Complaint.civic_issue_id == issue.id).all()
    max_severity = max((c.severity_hint or 2) for c in merged_complaints)
    has_verified_evidence = any(att.is_verified for c in merged_complaints for att in c.attachments)
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
    sla_record = sla_utils.upsert_sla(db, issue)
    db.flush()
    return {"issue": issue, "duplicate_info": duplicate_info, "location_matched": location_matched, "sla_record": sla_record, "priority": priority}
