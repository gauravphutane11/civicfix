from datetime import datetime, timezone
from pathlib import Path
import shutil
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas, sla_utils
from ..ai.evidence_matching import compare_evidence
from ..config import MAX_ACTIVE_CASES_PER_WORKER, UPLOAD_DIR
from ..database import get_db
from ..department_mapping import department_for_category
from ..security import require_roles
from ..worker_routing import (
    WORKER_AT_CAPACITY,
    fill_queue_for_category,
    refresh_worker_status,
    worker_case_count,
)

router = APIRouter(prefix="/field-officer", tags=["field-officer"])
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/jpg"}
MAX_IMAGE_SIZE = 8 * 1024 * 1024


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


def _load_issue(db: Session, issue_id: int, officer: models.User) -> models.CivicIssue:
    issue = (
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
    if not issue:
        raise HTTPException(404, "Civic issue not found")

    if issue.category != officer.service_category:
        raise HTTPException(403, "This case belongs to another service category.")

    if issue.assigned_to not in {None, officer.name, officer.email}:
        raise HTTPException(403, "This case is assigned to another worker.")
    return issue


def _out(issue: models.CivicIssue):
    issue.status_history.sort(key=lambda history: history.changed_at)
    issue.field_work_evidence.sort(key=lambda evidence: evidence.uploaded_at, reverse=True)
    issue.completion_evidence.sort(key=lambda evidence: evidence.uploaded_at, reverse=True)
    for complaint in issue.complaints:
        complaint.completion_evidence.sort(key=lambda evidence: evidence.uploaded_at, reverse=True)
    return issue


def _validate_photo(photo: UploadFile):
    if photo.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(400, f"Unsupported image type: {photo.content_type}")
    data = photo.file.read(MAX_IMAGE_SIZE + 1)
    photo.file.seek(0)
    if len(data) > MAX_IMAGE_SIZE:
        raise HTTPException(400, "Image must be 8 MB or smaller")
    try:
        with Image.open(photo.file) as image:
            image.verify()
    except (UnidentifiedImageError, OSError):
        photo.file.seek(0)
        raise HTTPException(400, "The camera capture is not a valid image.")
    finally:
        photo.file.seek(0)


def _save_photo(photo: UploadFile) -> str:
    ext = Path(photo.filename or "").suffix.lower() or ".jpg"
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        ext = ".jpg"
    path = UPLOAD_DIR / f"field_live_{uuid.uuid4().hex}{ext}"
    with path.open("wb") as handle:
        shutil.copyfileobj(photo.file, handle)
    return str(path)


def _best_match(db: Session, issue: models.CivicIssue, citizen):
    workers = (
        db.query(models.FieldWorkEvidence)
        .filter(models.FieldWorkEvidence.civic_issue_id == issue.id)
        .order_by(models.FieldWorkEvidence.uploaded_at.desc())
        .all()
    )
    best = None
    for worker in workers:
        result = compare_evidence(
            worker.file_path,
            worker.latitude,
            worker.longitude,
            citizen.file_path,
            citizen.latitude,
            citizen.longitude,
        )
        candidate = (result.verification_score, worker, result)
        if best is None or candidate[0] > best[0]:
            best = candidate
    return best


def _resolve_from_match(db: Session, issue: models.CivicIssue) -> None:
    now = datetime.now(timezone.utc)
    if issue.status != models.IssueStatus.RESOLVED.value:
        old = issue.status
        issue.status = models.IssueStatus.RESOLVED.value
        issue.resolved_at = now
        db.add(
            models.StatusHistory(
                civic_issue_id=issue.id,
                from_status=old,
                to_status=issue.status,
                changed_by="CivicFix Evidence Engine",
                note="Resolution verified from matched worker and citizen live-camera evidence.",
            )
        )
    if issue.sla_record:
        sla_utils.mark_resolved(issue.sla_record)
    _sync_complaint_statuses(issue)
    if issue.assigned_to:
        worker = db.query(models.User).filter(
            models.User.role == models.Role.FIELD_OFFICER.value,
            or_(models.User.name == issue.assigned_to, models.User.email == issue.assigned_to),
        ).first()
        if worker:
            refresh_worker_status(db, worker)
    fill_queue_for_category(db, issue.category)


def _match_pending_citizen_evidence(db: Session, issue: models.CivicIssue) -> None:
    pending = (
        db.query(models.CitizenCompletionEvidence)
        .filter(
            models.CitizenCompletionEvidence.civic_issue_id == issue.id,
            models.CitizenCompletionEvidence.verification_status.in_(
                [
                    models.CompletionEvidenceStatus.PENDING_WORKER_EVIDENCE.value,
                    models.CompletionEvidenceStatus.NEEDS_REVIEW.value,
                ]
            ),
        )
        .order_by(models.CitizenCompletionEvidence.uploaded_at.desc())
        .all()
    )
    for citizen in pending:
        best = _best_match(db, issue, citizen)
        if best is None:
            continue
        _, worker, match = best
        citizen.matched_field_evidence_id = worker.id
        citizen.visual_similarity = match.visual_similarity
        citizen.location_distance_meters = match.location_distance_meters
        citizen.location_score = match.location_score
        citizen.verification_score = match.verification_score
        citizen.verification_status = match.status
        citizen.verification_note = match.note
        if match.status == models.CompletionEvidenceStatus.VERIFIED.value:
            _resolve_from_match(db, issue)


@router.get("/overview", response_model=schemas.WorkerOverviewOut)
def overview(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(models.Role.FIELD_OFFICER.value)),
):
    if not current_user.service_category:
        raise HTTPException(409, "This worker account has no service category configured.")
    refresh_worker_status(db, current_user)
    siblings = (
        db.query(models.User)
        .filter(
            models.User.role == models.Role.FIELD_OFFICER.value,
            models.User.service_category == current_user.service_category,
            models.User.is_active.is_(True),
        )
        .order_by(models.User.id.asc())
        .all()
    )
    rows: list[schemas.WorkerRosterOut] = []
    for worker in siblings:
        active = refresh_worker_status(db, worker)
        queued = (
            db.query(models.CivicIssue)
            .filter(
                models.CivicIssue.category == current_user.service_category,
                models.CivicIssue.status == models.IssueStatus.OPEN.value,
                models.CivicIssue.assigned_to.is_(None),
            )
            .count()
        )
        codes = [
            issue.issue_code
            for issue in db.query(models.CivicIssue)
            .filter(
                models.CivicIssue.status.in_({models.IssueStatus.ASSIGNED.value, models.IssueStatus.IN_PROGRESS.value}),
                or_(models.CivicIssue.assigned_to == worker.name, models.CivicIssue.assigned_to == worker.email),
            )
            .order_by(models.CivicIssue.priority_score.desc())
            .all()
        ]
        rows.append(
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
                current_issue_codes=codes[:MAX_ACTIVE_CASES_PER_WORKER],
            )
        )

    category_open = db.query(models.CivicIssue).filter(
        models.CivicIssue.category == current_user.service_category,
        models.CivicIssue.status == models.IssueStatus.OPEN.value,
    ).count()
    category_active = db.query(models.CivicIssue).filter(
        models.CivicIssue.category == current_user.service_category,
        models.CivicIssue.status.in_({models.IssueStatus.ASSIGNED.value, models.IssueStatus.IN_PROGRESS.value}),
    ).count()
    category_resolved = db.query(models.CivicIssue).filter(
        models.CivicIssue.category == current_user.service_category,
        models.CivicIssue.status == models.IssueStatus.RESOLVED.value,
    ).count()
    db.commit()
    me = next(row for row in rows if row.id == current_user.id)
    return schemas.WorkerOverviewOut(
        worker=me,
        category=current_user.service_category,
        department=department_for_category(current_user.service_category),
        max_active_cases=MAX_ACTIVE_CASES_PER_WORKER,
        category_open_cases=category_open,
        category_active_cases=category_active,
        category_resolved_cases=category_resolved,
        sibling_workers=rows,
    )


@router.get("/issues", response_model=list[schemas.CivicIssueOut])
def my_issues(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(models.Role.FIELD_OFFICER.value)),
):
    if not current_user.service_category:
        raise HTTPException(409, "This worker account has no service category configured.")
    issues = (
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
        .filter(models.CivicIssue.category == current_user.service_category)
        .filter(
            or_(
                models.CivicIssue.assigned_to.is_(None),
                models.CivicIssue.assigned_to == current_user.name,
                models.CivicIssue.assigned_to == current_user.email,
            )
        )
        .order_by(models.CivicIssue.priority_score.desc(), models.CivicIssue.created_at.asc())
        .all()
    )
    changed = False
    for issue in issues:
        if issue.sla_record:
            before = issue.sla_record.state
            after = sla_utils.recompute_state(issue.sla_record)
            changed = changed or before != after
    if changed:
        db.commit()
    return [_out(issue) for issue in issues]


@router.get("/issues/{issue_id}", response_model=schemas.CivicIssueOut)
def issue_detail(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(models.Role.FIELD_OFFICER.value)),
):
    return _out(_load_issue(db, issue_id, current_user))


@router.post("/issues/{issue_id}/claim", response_model=schemas.CivicIssueOut)
def claim_issue(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(models.Role.FIELD_OFFICER.value)),
):
    issue = _load_issue(db, issue_id, current_user)
    if issue.assigned_to:
        raise HTTPException(409, "This case is already assigned to a worker.")
    active = worker_case_count(db, current_user)
    if active >= MAX_ACTIVE_CASES_PER_WORKER:
        raise HTTPException(409, "Your worker account is at capacity.")
    issue.department = department_for_category(issue.category)
    issue.assigned_to = current_user.name
    issue.assigned_at = datetime.now(timezone.utc)
    issue.assignment_source = "Worker Claim"
    issue.assignment_note = f"Claimed by {current_user.name}."
    old = issue.status
    issue.status = models.IssueStatus.ASSIGNED.value
    db.add(
        models.StatusHistory(
            civic_issue_id=issue.id,
            from_status=old,
            to_status=issue.status,
            changed_by=current_user.name,
            note="Unassigned category-queue case claimed by a matching worker.",
        )
    )
    _sync_complaint_statuses(issue)
    refresh_worker_status(db, current_user)
    db.commit()
    return _out(_load_issue(db, issue.id, current_user))


@router.patch("/issues/{issue_id}/status", response_model=schemas.CivicIssueOut)
def update_status(
    issue_id: int,
    payload: schemas.StatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(models.Role.FIELD_OFFICER.value)),
):
    issue = _load_issue(db, issue_id, current_user)
    allowed = {
        models.IssueStatus.ASSIGNED.value: {models.IssueStatus.IN_PROGRESS.value, models.IssueStatus.OPEN.value},
        models.IssueStatus.IN_PROGRESS.value: {models.IssueStatus.ASSIGNED.value},
    }
    if payload.status not in allowed.get(issue.status, set()):
        raise HTTPException(400, "Use Start Work first, then submit live completion evidence for verification.")
    if issue.assigned_to not in {current_user.name, current_user.email}:
        raise HTTPException(403, "This case is not assigned to your worker account.")

    old = issue.status
    issue.status = payload.status
    if payload.status == models.IssueStatus.OPEN.value:
        issue.assigned_to = None
        issue.assigned_at = None
        issue.assignment_source = "auto_queued"
        issue.assignment_note = "Released by field worker and returned to the category queue."
    db.add(
        models.StatusHistory(
            civic_issue_id=issue.id,
            from_status=old,
            to_status=issue.status,
            changed_by=current_user.name,
            note=payload.note or f"Updated by {current_user.name}",
        )
    )
    _sync_complaint_statuses(issue)
    refresh_worker_status(db, current_user)
    if payload.status == models.IssueStatus.ASSIGNED.value:
        issue.assignment_note = "Returned to assigned state by field worker."
    if payload.status == models.IssueStatus.OPEN.value:
        fill_queue_for_category(db, issue.category)
    db.commit()
    return _out(_load_issue(db, issue.id, current_user))


@router.post("/issues/{issue_id}/evidence", response_model=schemas.FieldWorkEvidenceOut)
def capture_evidence(
    issue_id: int,
    latitude: float = Form(...),
    longitude: float = Form(...),
    capture_mode: str = Form(...),
    note: Optional[str] = Form(None),
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(models.Role.FIELD_OFFICER.value)),
):
    issue = _load_issue(db, issue_id, current_user)
    if issue.assigned_to not in {current_user.name, current_user.email}:
        raise HTTPException(403, "This case is not assigned to your worker account.")
    if issue.status not in {models.IssueStatus.ASSIGNED.value, models.IssueStatus.IN_PROGRESS.value}:
        raise HTTPException(400, "Live completion evidence can only be captured for an assigned or in-progress case.")
    if capture_mode != "live_camera":
        raise HTTPException(400, "Only live camera completion evidence is accepted.")
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise HTTPException(400, "Invalid geotag coordinates")
    _validate_photo(photo)
    path = _save_photo(photo)

    evidence = models.FieldWorkEvidence(
        civic_issue_id=issue.id,
        officer_id=current_user.id,
        file_path=path,
        content_type=photo.content_type,
        capture_mode=capture_mode,
        latitude=latitude,
        longitude=longitude,
        note=(note or "").strip() or None,
    )
    db.add(evidence)
    db.flush()

    if issue.status == models.IssueStatus.ASSIGNED.value:
        old = issue.status
        issue.status = models.IssueStatus.IN_PROGRESS.value
        db.add(
            models.StatusHistory(
                civic_issue_id=issue.id,
                from_status=old,
                to_status=issue.status,
                changed_by=current_user.name,
                note="Work started; live geotagged completion evidence captured.",
            )
        )
    _sync_complaint_statuses(issue)
    _match_pending_citizen_evidence(db, issue)
    refresh_worker_status(db, current_user)
    db.commit()
    db.refresh(evidence)
    return schemas.FieldWorkEvidenceOut.model_validate(evidence)
