from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from .. import models, sla_utils
from ..database import get_db
from ..security import require_roles

router = APIRouter(prefix="/sla", tags=["sla"])

@router.get("/summary")
def sla_summary(db: Session = Depends(get_db), current_user: models.User = Depends(require_roles(models.Role.ADMIN.value, models.Role.FIELD_OFFICER.value))):
    issues = db.query(models.CivicIssue).all()
    for issue in issues:
        if issue.sla_record: sla_utils.recompute_state(issue.sla_record)
    db.commit()
    buckets = {"within_sla": [], "at_risk": [], "breached": [], "met": []}
    for issue in issues:
        if not issue.sla_record: continue
        buckets.setdefault(issue.sla_record.state, []).append({"issue_code": issue.issue_code, "category": issue.category, "priority_band": issue.priority_band, "status": issue.status, "due_at": issue.sla_record.due_at.isoformat(), "target_hours": issue.sla_record.target_hours, "location": issue.location_text_raw})
    cases = []
    for issue in sorted(
        issues,
        key=lambda item: (-(item.priority_score or 0), item.created_at),
    ):
        cases.append({
            "id": issue.id,
            "issue_code": issue.issue_code,
            "complaint_codes": [c.complaint_code for c in issue.complaints],
            "category": issue.category,
            "department": issue.department,
            "assigned_to": issue.assigned_to,
            "priority_score": issue.priority_score,
            "priority_band": issue.priority_band,
            "status": issue.status,
            "location": issue.location_text_raw,
            "latitude": issue.latitude,
            "longitude": issue.longitude,
            "complaint_count": issue.complaint_count,
            "due_at": issue.sla_record.due_at.isoformat() if issue.sla_record else None,
            "sla_state": issue.sla_record.state if issue.sla_record else None,
        })

    return {
        "counts": {k: len(v) for k, v in buckets.items()},
        "breached": buckets["breached"],
        "at_risk": buckets["at_risk"],
        "cases": cases,
    }
