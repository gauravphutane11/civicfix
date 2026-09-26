from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from .. import models, schemas, sla_utils
from ..database import get_db
from ..security import require_roles

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
OPEN_STATES = {models.IssueStatus.OPEN.value, models.IssueStatus.ASSIGNED.value, models.IssueStatus.IN_PROGRESS.value}

@router.get("/metrics", response_model=schemas.DashboardMetrics)
def get_metrics(db: Session = Depends(get_db), current_user: models.User = Depends(require_roles(models.Role.ADMIN.value, models.Role.FIELD_OFFICER.value))):
    issues = db.query(models.CivicIssue).all()
    for issue in issues:
        if issue.sla_record: sla_utils.recompute_state(issue.sla_record)
    db.commit()
    total_complaints = db.query(models.Complaint).count(); total_civic_issues = len(issues)
    open_issues = sum(1 for i in issues if i.status in OPEN_STATES)
    critical_issues = sum(1 for i in issues if i.priority_band == "CRITICAL")
    high_issues = sum(1 for i in issues if i.priority_band == "HIGH")
    resolved_issues = sum(1 for i in issues if i.status == models.IssueStatus.RESOLVED.value)
    duplicates_consolidated = max(0, total_complaints - total_civic_issues)
    sla_within = sum(1 for i in issues if i.sla_record and i.sla_record.state == "within_sla")
    sla_at_risk = sum(1 for i in issues if i.sla_record and i.sla_record.state == "at_risk")
    sla_breached = sum(1 for i in issues if i.sla_record and i.sla_record.state == "breached")
    resolved_with_sla = [i for i in issues if i.sla_record and i.sla_record.resolved_at is not None]
    met = sum(1 for i in resolved_with_sla if i.sla_record.state == "met")
    sla_compliance_pct = round((met / len(resolved_with_sla)) * 100, 1) if resolved_with_sla else 100.0
    resolution_hours = []
    for i in issues:
        if i.resolved_at:
            created = i.created_at if i.created_at.tzinfo else i.created_at.replace(tzinfo=timezone.utc)
            resolved = i.resolved_at if i.resolved_at.tzinfo else i.resolved_at.replace(tzinfo=timezone.utc)
            resolution_hours.append((resolved - created).total_seconds() / 3600)
    avg_resolution_hours = round(sum(resolution_hours) / len(resolution_hours), 1) if resolution_hours else None
    by_category, by_status = {}, {}
    for i in issues:
        by_category[i.category] = by_category.get(i.category, 0) + 1
        by_status[i.status] = by_status.get(i.status, 0) + 1
    return schemas.DashboardMetrics(total_complaints=total_complaints, total_civic_issues=total_civic_issues, open_issues=open_issues, critical_issues=critical_issues, high_issues=high_issues, resolved_issues=resolved_issues, duplicates_consolidated=duplicates_consolidated, sla_within=sla_within, sla_at_risk=sla_at_risk, sla_breached=sla_breached, sla_compliance_pct=sla_compliance_pct, avg_resolution_hours=avg_resolution_hours, by_category=by_category, by_status=by_status)

@router.get("/map", response_model=List[schemas.MapPoint])
def get_map_points(db: Session = Depends(get_db), current_user: models.User = Depends(require_roles(models.Role.ADMIN.value, models.Role.FIELD_OFFICER.value))):
    issues = db.query(models.CivicIssue).filter(models.CivicIssue.latitude.isnot(None), models.CivicIssue.longitude.isnot(None)).all()
    return [schemas.MapPoint(id=i.id, issue_code=i.issue_code, category=i.category, latitude=i.latitude, longitude=i.longitude, priority_band=i.priority_band, priority_score=i.priority_score, status=i.status, complaint_count=i.complaint_count, location_name=i.location_text_raw) for i in issues]
