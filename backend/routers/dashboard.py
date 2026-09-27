from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models, schemas, sla_utils
from ..config import MAX_ACTIVE_CASES_PER_WORKER
from ..database import get_db
from ..department_mapping import SERVICE_CATEGORIES, department_for_category
from ..security import require_roles
from ..worker_routing import (
    WORKER_AT_CAPACITY,
    WORKER_BUSY,
    WORKER_OFFLINE,
    WORKER_AVAILABLE,
    list_workers,
    queued_case_count,
    refresh_worker_status,
    worker_case_count,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
OPEN_STATES = {
    models.IssueStatus.OPEN.value,
    models.IssueStatus.ASSIGNED.value,
    models.IssueStatus.IN_PROGRESS.value,
}


@router.get("/metrics", response_model=schemas.DashboardMetrics)
def get_metrics(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        require_roles(models.Role.ADMIN.value, models.Role.FIELD_OFFICER.value)
    ),
):
    issues = db.query(models.CivicIssue).all()
    for issue in issues:
        if issue.sla_record:
            sla_utils.recompute_state(issue.sla_record)
    db.commit()

    total_complaints = db.query(models.Complaint).count()
    total_civic_issues = len(issues)
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
    for issue in issues:
        if issue.resolved_at:
            created = issue.created_at if issue.created_at.tzinfo else issue.created_at.replace(tzinfo=timezone.utc)
            resolved = issue.resolved_at if issue.resolved_at.tzinfo else issue.resolved_at.replace(tzinfo=timezone.utc)
            resolution_hours.append((resolved - created).total_seconds() / 3600)
    avg_resolution_hours = round(sum(resolution_hours) / len(resolution_hours), 1) if resolution_hours else None

    by_category: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for issue in issues:
        by_category[issue.category] = by_category.get(issue.category, 0) + 1
        by_status[issue.status] = by_status.get(issue.status, 0) + 1

    return schemas.DashboardMetrics(
        total_complaints=total_complaints,
        total_civic_issues=total_civic_issues,
        open_issues=open_issues,
        critical_issues=critical_issues,
        high_issues=high_issues,
        resolved_issues=resolved_issues,
        duplicates_consolidated=duplicates_consolidated,
        sla_within=sla_within,
        sla_at_risk=sla_at_risk,
        sla_breached=sla_breached,
        sla_compliance_pct=sla_compliance_pct,
        avg_resolution_hours=avg_resolution_hours,
        by_category=by_category,
        by_status=by_status,
    )


@router.get("/map", response_model=List[schemas.MapPoint])
def get_map_points(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        require_roles(models.Role.ADMIN.value, models.Role.FIELD_OFFICER.value)
    ),
):
    issues = (
        db.query(models.CivicIssue)
        .filter(models.CivicIssue.latitude.isnot(None), models.CivicIssue.longitude.isnot(None))
        .all()
    )
    return [
        schemas.MapPoint(
            id=issue.id,
            issue_code=issue.issue_code,
            category=issue.category,
            latitude=issue.latitude,
            longitude=issue.longitude,
            priority_band=issue.priority_band,
            priority_score=issue.priority_score,
            status=issue.status,
            complaint_count=issue.complaint_count,
            location_name=issue.location_text_raw,
        )
        for issue in issues
    ]


@router.get("/workers", response_model=list[schemas.WorkerRosterOut])
def get_worker_roster(
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(models.Role.ADMIN.value)),
):
    if category and category not in SERVICE_CATEGORIES:
        raise HTTPException(400, "Unknown worker service category")

    workers = list_workers(db, category)
    roster: list[schemas.WorkerRosterOut] = []
    for worker in workers:
        active = worker_case_count(db, worker)
        queued = queued_case_count(db, worker.service_category or "") if worker.service_category else 0
        current_issue_codes = [
            issue.issue_code
            for issue in db.query(models.CivicIssue)
            .filter(
                models.CivicIssue.status.in_({models.IssueStatus.ASSIGNED.value, models.IssueStatus.IN_PROGRESS.value}),
                or_(models.CivicIssue.assigned_to == worker.name, models.CivicIssue.assigned_to == worker.email),
            )
            .order_by(models.CivicIssue.priority_score.desc(), models.CivicIssue.created_at.asc())
            .all()
        ]
        roster.append(
            schemas.WorkerRosterOut(
                id=worker.id,
                name=worker.name,
                email=worker.email,
                role=worker.role,
                service_category=worker.service_category,
                department=worker.department,
                availability_status=worker.availability_status,
                is_active=bool(worker.is_active),
                active_cases=active,
                queued_cases=queued,
                current_issue_codes=current_issue_codes[:MAX_ACTIVE_CASES_PER_WORKER],
            )
        )
    db.commit()
    return roster


@router.get("/workers/summary", response_model=dict)
def get_worker_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(models.Role.ADMIN.value)),
):
    workers = list_workers(db)
    summary = []
    for category in SERVICE_CATEGORIES:
        category_workers = [worker for worker in workers if worker.service_category == category]
        active = sum(worker_case_count(db, worker) for worker in category_workers)
        available = sum(1 for worker in category_workers if worker.availability_status == WORKER_AVAILABLE)
        busy = sum(1 for worker in category_workers if worker.availability_status == WORKER_BUSY)
        at_capacity = sum(1 for worker in category_workers if worker.availability_status == WORKER_AT_CAPACITY)
        queued = queued_case_count(db, category)
        summary.append(
            {
                "category": category,
                "department": department_for_category(category),
                "workers": len(category_workers),
                "available": available,
                "busy": busy,
                "at_capacity": at_capacity,
                "active_cases": active,
                "queued_cases": queued,
            }
        )
    db.commit()
    return {"max_active_cases_per_worker": MAX_ACTIVE_CASES_PER_WORKER, "categories": summary}
