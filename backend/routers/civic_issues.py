from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas, sla_utils
from ..database import get_db
from ..department_mapping import DEPARTMENT_NAMES, department_for_category
from ..config import MAX_ACTIVE_CASES_PER_WORKER
from ..security import get_current_user, require_roles
from ..worker_routing import (
    fill_queue_for_category,
    refresh_worker_status,
    worker_case_count,
)

router = APIRouter(prefix="/civic-issues", tags=["civic-issues"])

VALID_TRANSITIONS = {
    models.IssueStatus.OPEN.value: {
        models.IssueStatus.ASSIGNED.value,
        models.IssueStatus.REJECTED.value,
    },
    models.IssueStatus.ASSIGNED.value: {
        models.IssueStatus.IN_PROGRESS.value,
        models.IssueStatus.OPEN.value,
    },
    models.IssueStatus.IN_PROGRESS.value: {
        models.IssueStatus.RESOLVED.value,
        models.IssueStatus.ASSIGNED.value,
    },
    models.IssueStatus.RESOLVED.value: set(),
    models.IssueStatus.REJECTED.value: set(),
}


def _sync_complaint_statuses(issue: models.CivicIssue) -> None:
    status_map = {
        models.IssueStatus.OPEN.value: models.ComplaintStatus.OPEN.value,
        models.IssueStatus.ASSIGNED.value: models.ComplaintStatus.ASSIGNED.value,
        models.IssueStatus.IN_PROGRESS.value: models.ComplaintStatus.IN_PROGRESS.value,
        models.IssueStatus.RESOLVED.value: models.ComplaintStatus.RESOLVED.value,
        models.IssueStatus.REJECTED.value: models.ComplaintStatus.REJECTED.value,
    }
    mapped = status_map.get(issue.status)
    if mapped is None:
        return
    for complaint in issue.complaints:
        complaint.status = mapped


def _touch_sla_states(issues, db: Session):
    changed = False
    for issue in issues:
        if issue.sla_record:
            before = issue.sla_record.state
            after = sla_utils.recompute_state(issue.sla_record)
            changed = changed or before != after
    if changed:
        db.commit()


def _load_issue(db: Session, issue_id: int):
    return (
        db.query(models.CivicIssue)
        .options(
            joinedload(models.CivicIssue.complaints).joinedload(models.Complaint.attachments),
            joinedload(models.CivicIssue.complaints).joinedload(models.Complaint.citizen),
            joinedload(models.CivicIssue.complaints).joinedload(models.Complaint.work_review),
            joinedload(models.CivicIssue.complaints).joinedload(models.Complaint.completion_evidence),
            joinedload(models.CivicIssue.field_work_evidence),
            joinedload(models.CivicIssue.completion_evidence),
            joinedload(models.CivicIssue.status_history),
            joinedload(models.CivicIssue.sla_record),
        )
        .filter(models.CivicIssue.id == issue_id)
        .first()
    )


@router.get("", response_model=List[schemas.CivicIssueSummary])
def list_civic_issues(
    q: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    priority_band: Optional[str] = None,
    min_score: Optional[int] = None,
    department: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        require_roles(models.Role.ADMIN.value, models.Role.FIELD_OFFICER.value)
    ),
):
    query = (
        db.query(models.CivicIssue)
        .options(joinedload(models.CivicIssue.sla_record))
        .outerjoin(models.CivicIssue.complaints)
        .outerjoin(models.Complaint.citizen)
    )

    if q:
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                models.CivicIssue.issue_code.ilike(term),
                models.CivicIssue.representative_text.ilike(term),
                models.CivicIssue.location_text_raw.ilike(term),
                models.Complaint.complaint_code.ilike(term),
                models.Complaint.raw_text.ilike(term),
                models.User.name.ilike(term),
                models.User.email.ilike(term),
                models.User.phone.ilike(term),
            )
        )

    if category:
        query = query.filter(models.CivicIssue.category == category)
    if status:
        query = query.filter(models.CivicIssue.status == status)
    if priority_band:
        query = query.filter(models.CivicIssue.priority_band == priority_band)
    if min_score is not None:
        query = query.filter(models.CivicIssue.priority_score >= min_score)
    if department:
        if department not in DEPARTMENT_NAMES:
            raise HTTPException(400, "Unknown department")
        query = query.filter(models.CivicIssue.department == department)

    issues = (
        query.order_by(
            models.CivicIssue.priority_score.desc(),
            models.CivicIssue.created_at.asc(),
        )
        .all()
    )
    _touch_sla_states(issues, db)
    return issues


@router.get("/{issue_id}", response_model=schemas.CivicIssueOut)
def get_civic_issue(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    issue = _load_issue(db, issue_id)
    if not issue:
        raise HTTPException(404, "Civic issue not found")

    if current_user.role not in {
        models.Role.ADMIN.value,
        models.Role.FIELD_OFFICER.value,
    }:
        owns_issue = any(
            complaint.citizen_id == current_user.id for complaint in issue.complaints
        )
        if not owns_issue:
            raise HTTPException(403, "You can only view civic cases linked to your reports")

    if issue.sla_record:
        sla_utils.recompute_state(issue.sla_record)

    issue.status_history.sort(key=lambda history: history.changed_at)
    issue.field_work_evidence.sort(key=lambda evidence: evidence.uploaded_at, reverse=True)
    issue.completion_evidence.sort(key=lambda evidence: evidence.uploaded_at, reverse=True)
    for complaint in issue.complaints:
        complaint.completion_evidence.sort(
            key=lambda evidence: evidence.uploaded_at, reverse=True
        )
    db.commit()
    return issue


@router.patch("/{issue_id}/status", response_model=schemas.CivicIssueOut)
def update_status(
    issue_id: int,
    payload: schemas.StatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        require_roles(models.Role.ADMIN.value, models.Role.FIELD_OFFICER.value)
    ),
):
    issue = db.get(models.CivicIssue, issue_id)
    if not issue:
        raise HTTPException(404, "Civic issue not found")

    new_status = payload.status
    if new_status not in VALID_TRANSITIONS:
        raise HTTPException(400, f"Unknown status '{new_status}'")
    if new_status != issue.status and new_status not in VALID_TRANSITIONS[issue.status]:
        raise HTTPException(400, f"Cannot move issue from '{issue.status}' to '{new_status}'.")

    if current_user.role == models.Role.FIELD_OFFICER.value:
        if issue.category != current_user.service_category:
            raise HTTPException(403, "This case belongs to another service category.")
        if issue.assigned_to not in {current_user.name, current_user.email}:
            raise HTTPException(403, "This case is not assigned to your worker account.")

    actor = current_user.name if current_user.role != models.Role.ADMIN.value else (payload.changed_by or current_user.name)
    old_status = issue.status
    issue.status = new_status
    if new_status == models.IssueStatus.RESOLVED.value:
        issue.resolved_at = datetime.now(timezone.utc)
        if issue.sla_record:
            sla_utils.mark_resolved(issue.sla_record)
    elif old_status == models.IssueStatus.RESOLVED.value and new_status != old_status:
        issue.resolved_at = None
        if issue.sla_record:
            issue.sla_record.resolved_at = None
            sla_utils.recompute_state(issue.sla_record)

    db.add(
        models.StatusHistory(
            civic_issue_id=issue.id,
            from_status=old_status,
            to_status=new_status,
            changed_by=actor,
            note=payload.note,
        )
    )
    _sync_complaint_statuses(issue)
    if issue.assigned_to:
        worker = db.query(models.User).filter(
            models.User.role == models.Role.FIELD_OFFICER.value,
            or_(models.User.name == issue.assigned_to, models.User.email == issue.assigned_to),
        ).first()
        if worker:
            refresh_worker_status(db, worker)
    if new_status in {models.IssueStatus.RESOLVED.value, models.IssueStatus.REJECTED.value}:
        fill_queue_for_category(db, issue.category)
    db.commit()
    return get_civic_issue(issue_id, db, current_user)


@router.patch("/{issue_id}/assign", response_model=schemas.CivicIssueOut)
def assign_issue(
    issue_id: int,
    payload: schemas.AssignmentUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(models.Role.ADMIN.value)),
):
    issue = db.get(models.CivicIssue, issue_id)
    if not issue:
        raise HTTPException(404, "Civic issue not found")

    canonical_department = department_for_category(issue.category)
    issue.department = canonical_department
    assigned_value = (payload.assigned_to or "").strip()
    if not assigned_value:
        raise HTTPException(400, "A worker account is required for assignment.")

    officer = (
        db.query(models.User)
        .filter(models.User.role == models.Role.FIELD_OFFICER.value)
        .filter(or_(models.User.name == assigned_value, models.User.email == assigned_value))
        .first()
    )
    if officer is None:
        raise HTTPException(404, "Field worker account not found")
    if not officer.is_active:
        raise HTTPException(400, "This worker account is inactive.")
    if officer.service_category != issue.category:
        raise HTTPException(400, "This worker is not provisioned for the AI-classified issue category.")

    if officer.name != issue.assigned_to:
        active_count = worker_case_count(db, officer)
        if active_count >= MAX_ACTIVE_CASES_PER_WORKER:
            raise HTTPException(409, "This worker is currently at capacity. Choose the other category worker or leave the case queued.")

    previous_assigned = issue.assigned_to
    issue.assigned_to = officer.name
    issue.department = canonical_department
    issue.assigned_at = datetime.now(timezone.utc)
    issue.assignment_source = "Admin Console"
    issue.assignment_note = f"Manually assigned by {current_user.name}."
    old_status = issue.status
    if issue.status == models.IssueStatus.OPEN.value:
        issue.status = models.IssueStatus.ASSIGNED.value
        db.add(
            models.StatusHistory(
                civic_issue_id=issue.id,
                from_status=old_status,
                to_status=issue.status,
                changed_by=current_user.name,
                note=f"Assigned to {officer.name} ({canonical_department}).",
            )
        )

    _sync_complaint_statuses(issue)
    if previous_assigned and previous_assigned != officer.name:
        previous = db.query(models.User).filter(
            models.User.role == models.Role.FIELD_OFFICER.value,
            or_(models.User.name == previous_assigned, models.User.email == previous_assigned),
        ).first()
        if previous:
            refresh_worker_status(db, previous)
    refresh_worker_status(db, officer)
    db.commit()
    return get_civic_issue(issue_id, db, current_user)


@router.patch(
    "/{issue_id}/completion-evidence/{evidence_id}/decision",
    response_model=schemas.CompletionEvidenceResponse,
)
def decide_completion_evidence(
    issue_id: int,
    evidence_id: int,
    payload: schemas.CompletionEvidenceDecision,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(models.Role.ADMIN.value)),
):
    issue = db.get(models.CivicIssue, issue_id)
    if not issue:
        raise HTTPException(404, "Civic issue not found")

    evidence = (
        db.query(models.CitizenCompletionEvidence)
        .filter(
            models.CitizenCompletionEvidence.id == evidence_id,
            models.CitizenCompletionEvidence.civic_issue_id == issue_id,
        )
        .first()
    )
    if not evidence:
        raise HTTPException(404, "Completion evidence not found")

    was_auto_verified = evidence.verification_status == models.CompletionEvidenceStatus.VERIFIED.value
    now = datetime.now(timezone.utc)
    evidence.reviewed_by = current_user.name
    evidence.reviewed_at = now
    evidence.verification_note = (
        payload.note.strip() if payload.note and payload.note.strip() else None
    )

    if payload.approved:
        evidence.verification_status = models.CompletionEvidenceStatus.ADMIN_CONFIRMED.value
        _sync_complaint_statuses(issue)
        if issue.status != models.IssueStatus.RESOLVED.value:
            old_status = issue.status
            issue.status = models.IssueStatus.RESOLVED.value
            issue.resolved_at = now
            db.add(
                models.StatusHistory(
                    civic_issue_id=issue.id,
                    from_status=old_status,
                    to_status=models.IssueStatus.RESOLVED.value,
                    changed_by=current_user.name,
                    note="Admin confirmed citizen/worker completion evidence.",
                )
            )
        if issue.sla_record:
            sla_utils.mark_resolved(issue.sla_record)
        _sync_complaint_statuses(issue)
    else:
        evidence.verification_status = models.CompletionEvidenceStatus.REJECTED.value
        if was_auto_verified and issue.status == models.IssueStatus.RESOLVED.value:
            old_status = issue.status
            issue.status = models.IssueStatus.IN_PROGRESS.value
            issue.resolved_at = None
            if issue.sla_record:
                issue.sla_record.resolved_at = None
                sla_utils.recompute_state(issue.sla_record)
            db.add(
                models.StatusHistory(
                    civic_issue_id=issue.id,
                    from_status=old_status,
                    to_status=models.IssueStatus.IN_PROGRESS.value,
                    changed_by=current_user.name,
                    note="Auto-verification rejected by admin; field work requires review.",
                )
            )
            _sync_complaint_statuses(issue)

    if issue.assigned_to:
        worker = db.query(models.User).filter(
            models.User.role == models.Role.FIELD_OFFICER.value,
            or_(models.User.name == issue.assigned_to, models.User.email == issue.assigned_to),
        ).first()
        if worker:
            refresh_worker_status(db, worker)
    if issue.status in {models.IssueStatus.RESOLVED.value, models.IssueStatus.REJECTED.value}:
        fill_queue_for_category(db, issue.category)
    db.commit()
    db.refresh(evidence)
    return schemas.CompletionEvidenceResponse(
        evidence=schemas.CompletionEvidenceOut.model_validate(evidence),
        issue_status=issue.status,
        admin_confirmation_pending=False,
    )
