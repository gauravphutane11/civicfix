import shutil
import uuid
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, Depends, Form, UploadFile, File, HTTPException
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..database import get_db
from ..config import UPLOAD_DIR
from ..ai.pipeline import run_triage
from ..ai.location import extract_location
from ..ai.image_analysis import analyze_image
from ..ai.evidence_matching import compare_evidence
from ..security import get_current_user, require_roles
from ..worker_routing import fill_queue_for_category, refresh_worker_status

router = APIRouter(prefix="/complaints", tags=["complaints"])
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/jpg"}
MAX_IMAGE_SIZE = 8 * 1024 * 1024
MAX_REVIEW_LENGTH = 500


def _save_upload(file: UploadFile, prefix: str = "") -> str:
    ext = Path(file.filename or "").suffix.lower() or ".jpg"
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        ext = ".jpg"
    fname = f"{prefix}{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / fname
    with dest.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)
    return str(dest)


def _validate_image_file(file: UploadFile) -> bytes:
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(400, f"Unsupported image type: {file.content_type}")
    data = file.file.read(MAX_IMAGE_SIZE + 1)
    file.file.seek(0)
    if len(data) > MAX_IMAGE_SIZE:
        raise HTTPException(400, "Image must be 8 MB or smaller")
    try:
        with Image.open(file.file) as image:
            image.verify()
    except (UnidentifiedImageError, OSError):
        file.file.seek(0)
        raise HTTPException(400, "The uploaded file is not a valid image.")
    finally:
        file.file.seek(0)
    return data


def _sync_issue_complaints(issue: models.CivicIssue) -> None:
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


def _mark_issue_resolved(
    db: Session,
    issue: models.CivicIssue,
    changed_by: str,
    note: str,
) -> None:
    from datetime import datetime, timezone

    if issue.status != models.IssueStatus.RESOLVED.value:
        old_status = issue.status
        issue.status = models.IssueStatus.RESOLVED.value
        issue.resolved_at = datetime.now(timezone.utc)
        db.add(
            models.StatusHistory(
                civic_issue_id=issue.id,
                from_status=old_status,
                to_status=models.IssueStatus.RESOLVED.value,
                changed_by=changed_by,
                note=note,
            )
        )
    elif issue.resolved_at is None:
        issue.resolved_at = datetime.now(timezone.utc)

    if issue.sla_record:
        from .. import sla_utils
        sla_utils.mark_resolved(issue.sla_record)

    _sync_issue_complaints(issue)
    if issue.assigned_to:
        worker = db.query(models.User).filter(
            models.User.role == models.Role.FIELD_OFFICER.value,
            models.User.name == issue.assigned_to,
        ).first()
        if worker:
            refresh_worker_status(db, worker)
    fill_queue_for_category(db, issue.category)


def _best_worker_evidence_match(
    db: Session,
    issue: models.CivicIssue,
    citizen_path: str,
    citizen_latitude: float,
    citizen_longitude: float,
):
    evidences = (
        db.query(models.FieldWorkEvidence)
        .filter(models.FieldWorkEvidence.civic_issue_id == issue.id)
        .order_by(models.FieldWorkEvidence.uploaded_at.desc())
        .all()
    )
    best = None
    for worker in evidences:
        result = compare_evidence(
            worker.file_path,
            worker.latitude,
            worker.longitude,
            citizen_path,
            citizen_latitude,
            citizen_longitude,
        )
        candidate = (result.verification_score, worker, result)
        if best is None or candidate[0] > best[0]:
            best = candidate
    return best


def _process_pending_citizen_evidence(
    db: Session,
    issue: models.CivicIssue,
    changed_by: str = "CivicFix Evidence Engine",
) -> None:
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

    for evidence in pending:
        best = _best_worker_evidence_match(
            db,
            issue,
            evidence.file_path,
            evidence.latitude,
            evidence.longitude,
        )
        if best is None:
            evidence.verification_status = models.CompletionEvidenceStatus.PENDING_WORKER_EVIDENCE.value
            evidence.verification_note = "Waiting for field-officer completion evidence."
            continue

        _, worker, match = best
        evidence.matched_field_evidence_id = worker.id
        evidence.visual_similarity = match.visual_similarity
        evidence.location_distance_meters = match.location_distance_meters
        evidence.location_score = match.location_score
        evidence.verification_score = match.verification_score
        evidence.verification_status = match.status
        evidence.verification_note = match.note

        if match.status == models.CompletionEvidenceStatus.VERIFIED.value:
            _mark_issue_resolved(
                db,
                issue,
                changed_by,
                "Resolution auto-confirmed by matched worker and citizen completion evidence.",
            )


def _load_complaint_for_response(db: Session, complaint_id: int):
    return (
        db.query(models.Complaint)
        .options(
            joinedload(models.Complaint.attachments),
            joinedload(models.Complaint.citizen),
            joinedload(models.Complaint.work_review),
            joinedload(models.Complaint.completion_evidence),
        )
        .filter(models.Complaint.id == complaint_id)
        .first()
    )


@router.post("", response_model=schemas.ComplaintSubmitResponse)
def create_complaint(
    raw_text: str = Form(...),
    language: Optional[str] = Form(None),
    citizen_name: Optional[str] = Form(None),
    citizen_phone: Optional[str] = Form(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    photo_latitude: Optional[float] = Form(None),
    photo_longitude: Optional[float] = Form(None),
    photo_capture_mode: str = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(models.Role.CITIZEN.value)),
):
    raw_text = raw_text.strip()
    if len(raw_text) < 8:
        raise HTTPException(400, "Please describe the issue in a bit more detail.")
    if photo_capture_mode != "live_camera":
        raise HTTPException(400, "CivicFix accepts only live camera photos for complaint evidence.")

    if (latitude is None) != (longitude is None):
        raise HTTPException(400, "Location coordinates must include both latitude and longitude.")
    if latitude is not None and longitude is not None:
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise HTTPException(400, "The supplied location coordinates are invalid.")
    else:
        location = extract_location(raw_text)
        if not location.matched:
            raise HTTPException(
                400,
                "Location is required. Use 'Use my location' or mention a specific landmark, gate, road, junction, or recognizable place in your report.",
            )

    complaint = models.Complaint(
        citizen_id=current_user.id,
        raw_text=raw_text,
        latitude=latitude,
        longitude=longitude,
    )
    db.add(complaint)
    db.flush()
    triage = run_triage(db, complaint, language_hint=language)

    _validate_image_file(image)
    saved_path = _save_upload(image)
    analysis = analyze_image(saved_path, complaint.category or "other")
    if not analysis.relevant:
        Path(saved_path).unlink(missing_ok=True)
        db.rollback()
        raise HTTPException(
            422,
            analysis.rejection_reason or "Please upload a clear photo of the civic problem.",
        )

    if (photo_latitude is None) != (photo_longitude is None):
        Path(saved_path).unlink(missing_ok=True)
        db.rollback()
        raise HTTPException(400, "Photo coordinates must include both latitude and longitude.")
    if photo_latitude is not None and photo_longitude is not None:
        if not (-90 <= photo_latitude <= 90 and -180 <= photo_longitude <= 180):
            Path(saved_path).unlink(missing_ok=True)
            db.rollback()
            raise HTTPException(400, "The supplied photo coordinates are invalid.")
        if latitude is not None and longitude is not None:
            from ..ai.evidence_matching import haversine_meters
            photo_distance = haversine_meters(latitude, longitude, photo_latitude, photo_longitude)
            if photo_distance > 50:
                Path(saved_path).unlink(missing_ok=True)
                db.rollback()
                raise HTTPException(400, f"Photo location is {round(photo_distance)} m away from the reported location. Please capture the civic evidence at the issue location.")

    attachment = models.Attachment(
        complaint_id=complaint.id,
        file_path=saved_path,
        content_type=image.content_type,
        latitude=photo_latitude,
        longitude=photo_longitude,
        capture_mode=photo_capture_mode,
        ai_tags=analysis.tags,
        ai_confidence=analysis.supporting_confidence,
        ai_notes=(
            f"brightness={analysis.brightness}, "
            f"edge_density={analysis.edge_density}, "
            f"color_variance={analysis.color_variance}, "
            f"document_score={analysis.document_score}, "
            f"face_dominance={analysis.face_dominance}, "
            f"civic_relevance={analysis.civic_relevance}"
        ),
    )
    db.add(attachment)
    db.flush()

    db.commit()
    complaint = _load_complaint_for_response(db, complaint.id)
    issue = triage["issue"]
    sla_record = triage["sla_record"]
    return schemas.ComplaintSubmitResponse(
        complaint=schemas.ComplaintOut.model_validate(complaint),
        civic_issue_code=issue.issue_code,
        civic_issue_id=issue.id,
        priority_score=issue.priority_score,
        priority_band=issue.priority_band,
        priority_breakdown=issue.priority_breakdown,
        duplicate_info=schemas.DuplicateInfoOut(**triage["duplicate_info"]),
        location_matched=triage["location_matched"],
        sla_due_at=sla_record.due_at,
        sla_target_hours=sla_record.target_hours,
        historical_context=triage.get("historical_context"),
        ai_explanation=triage.get("ai_explanation"),
        input_language=triage.get("input_language"),
        input_language_name=triage.get("input_language_name"),
        language_confidence=triage.get("language_confidence"),
        normalized_text=triage.get("normalized_text"),
        classification_method=triage.get("classification_method"),
        department=issue.department,
        assigned_to=issue.assigned_to,
        assignment_source=issue.assignment_source,
        assignment_note=issue.assignment_note,
    )


@router.get("", response_model=List[schemas.ComplaintOut])
def list_complaints(
    category: Optional[str] = None,
    status: Optional[str] = None,
    civic_issue_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        require_roles(models.Role.ADMIN.value, models.Role.FIELD_OFFICER.value)
    ),
):
    query = db.query(models.Complaint).options(
        joinedload(models.Complaint.attachments),
        joinedload(models.Complaint.citizen),
        joinedload(models.Complaint.work_review),
        joinedload(models.Complaint.completion_evidence),
    )
    if category:
        query = query.filter(models.Complaint.category == category)
    if status:
        query = query.filter(models.Complaint.status == status)
    if civic_issue_id:
        query = query.filter(models.Complaint.civic_issue_id == civic_issue_id)
    return query.order_by(models.Complaint.created_at.desc()).all()


@router.get("/mine", response_model=List[schemas.ComplaintOut])
def list_my_complaints(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(models.Role.CITIZEN.value)),
):
    return (
        db.query(models.Complaint)
        .options(
            joinedload(models.Complaint.attachments),
            joinedload(models.Complaint.citizen),
            joinedload(models.Complaint.work_review),
            joinedload(models.Complaint.completion_evidence),
        )
        .filter(models.Complaint.citizen_id == current_user.id)
        .order_by(models.Complaint.created_at.desc())
        .all()
    )


@router.post("/{complaint_code}/review", response_model=schemas.ComplaintOut)
def review_completed_work(
    complaint_code: str,
    payload: schemas.WorkReviewCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(models.Role.CITIZEN.value)),
):
    complaint = (
        db.query(models.Complaint)
        .options(
            joinedload(models.Complaint.civic_issue),
            joinedload(models.Complaint.work_review),
        )
        .filter(models.Complaint.complaint_code == complaint_code)
        .first()
    )
    if not complaint:
        raise HTTPException(404, "Complaint not found")
    if complaint.citizen_id != current_user.id:
        raise HTTPException(403, "You can only review your own complaint.")
    issue = complaint.civic_issue
    if not issue or issue.status != models.IssueStatus.RESOLVED.value:
        raise HTTPException(400, "You can review the ground work after this complaint is marked completed.")
    if complaint.work_review is not None:
        raise HTTPException(409, "You have already reviewed the completed work for this complaint.")

    evidence = (
        db.query(models.FieldWorkEvidence)
        .filter(models.FieldWorkEvidence.civic_issue_id == issue.id)
        .order_by(models.FieldWorkEvidence.uploaded_at.desc())
        .first()
    )
    review = models.WorkReview(
        complaint_id=complaint.id,
        civic_issue_id=issue.id,
        citizen_id=current_user.id,
        officer_id=evidence.officer_id if evidence else None,
        rating=payload.rating,
        review=payload.review,
    )
    db.add(review)
    db.commit()
    refreshed = _load_complaint_for_response(db, complaint.id)
    return schemas.ComplaintOut.model_validate(refreshed)


@router.post("/{complaint_code}/completion-evidence", response_model=schemas.CompletionEvidenceResponse)
def upload_citizen_completion_evidence(
    complaint_code: str,
    latitude: float = Form(...),
    longitude: float = Form(...),
    note: Optional[str] = Form(None),
    capture_mode: str = Form(...),
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(models.Role.CITIZEN.value)),
):
    complaint = (
        db.query(models.Complaint)
        .options(joinedload(models.Complaint.civic_issue))
        .filter(models.Complaint.complaint_code == complaint_code)
        .first()
    )
    if not complaint:
        raise HTTPException(404, "Complaint not found")
    if complaint.citizen_id != current_user.id:
        raise HTTPException(403, "You can only upload evidence for your own complaint.")
    if not complaint.civic_issue:
        raise HTTPException(400, "This complaint is not linked to an operational civic case yet.")
    if complaint.civic_issue.status == models.IssueStatus.REJECTED.value:
        raise HTTPException(400, "Evidence cannot be uploaded for a rejected civic case.")
    if complaint.civic_issue.status == models.IssueStatus.OPEN.value:
        raise HTTPException(400, "Wait until field work has been assigned before uploading an after-work confirmation photo.")
    if capture_mode != "live_camera":
        raise HTTPException(400, "CivicFix accepts only live camera photos for after-work evidence.")
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise HTTPException(400, "Invalid geotag coordinates")
    _validate_image_file(photo)

    saved_path = _save_upload(photo, prefix="citizen_")
    evidence = models.CitizenCompletionEvidence(
        complaint_id=complaint.id,
        civic_issue_id=complaint.civic_issue.id,
        citizen_id=current_user.id,
        file_path=saved_path,
        content_type=photo.content_type,
        capture_mode=capture_mode,
        latitude=latitude,
        longitude=longitude,
    )
    # CitizenCompletionEvidence intentionally has no separate note column in the
    # data model; keep an audit-friendly verification note instead.
    if note and note.strip():
        evidence.verification_note = f"Citizen note: {note.strip()[:400]}"
    db.add(evidence)
    db.flush()

    issue = complaint.civic_issue
    best = _best_worker_evidence_match(
        db, issue, saved_path, latitude, longitude
    )
    admin_pending = False
    if best is None:
        evidence.verification_status = models.CompletionEvidenceStatus.PENDING_WORKER_EVIDENCE.value
        evidence.verification_note = "Citizen evidence saved. Waiting for field-officer completion evidence."
    else:
        _, worker, match = best
        evidence.matched_field_evidence_id = worker.id
        evidence.visual_similarity = match.visual_similarity
        evidence.location_distance_meters = match.location_distance_meters
        evidence.location_score = match.location_score
        evidence.verification_score = match.verification_score
        evidence.verification_status = match.status
        evidence.verification_note = match.note
        if match.status == models.CompletionEvidenceStatus.VERIFIED.value:
            _mark_issue_resolved(
                db,
                issue,
                "CivicFix Evidence Engine",
                "Resolution auto-confirmed by matched worker and citizen completion evidence.",
            )
        else:
            admin_pending = True

    db.commit()
    db.refresh(evidence)
    return schemas.CompletionEvidenceResponse(
        evidence=schemas.CompletionEvidenceOut.model_validate(evidence),
        issue_status=issue.status,
        admin_confirmation_pending=admin_pending,
    )


@router.patch("/attachments/{attachment_id}/verify")
def verify_attachment(
    attachment_id: int,
    verified: bool = True,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(models.Role.ADMIN.value)),
):
    attachment = db.get(models.Attachment, attachment_id)
    if not attachment:
        raise HTTPException(404, "Attachment not found")
    attachment.is_verified = verified
    db.commit()
    db.refresh(attachment)
    return {"id": attachment.id, "is_verified": attachment.is_verified}


@router.get("/{complaint_code}", response_model=schemas.ComplaintOut)
def get_complaint(
    complaint_code: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    complaint = (
        db.query(models.Complaint)
        .options(
            joinedload(models.Complaint.attachments),
            joinedload(models.Complaint.citizen),
            joinedload(models.Complaint.work_review),
            joinedload(models.Complaint.completion_evidence),
        )
        .filter(models.Complaint.complaint_code == complaint_code)
        .first()
    )
    if not complaint:
        raise HTTPException(404, "Complaint not found")
    if current_user.role not in {models.Role.ADMIN.value, models.Role.FIELD_OFFICER.value} and complaint.citizen_id != current_user.id:
        raise HTTPException(403, "You can only view your own complaints")
    return complaint


@router.post("/{complaint_code}/analyze", response_model=schemas.ComplaintOut)
def reanalyze_complaint(
    complaint_code: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        require_roles(models.Role.ADMIN.value, models.Role.FIELD_OFFICER.value)
    ),
):
    complaint = db.query(models.Complaint).filter(models.Complaint.complaint_code == complaint_code).first()
    if not complaint:
        raise HTTPException(404, "Complaint not found")
    from ..ai.classifier import classifier

    result = classifier.classify(complaint.raw_text)
    complaint.category = result.category
    complaint.category_confidence = result.confidence
    complaint.category_terms = result.key_terms
    complaint.severity_hint = result.severity_hint
    loc = extract_location(complaint.raw_text)
    if loc.matched:
        complaint.location_text_raw = loc.place_name
        complaint.location_confidence = loc.confidence
        complaint.latitude = loc.latitude
        complaint.longitude = loc.longitude
    db.commit()
    refreshed = _load_complaint_for_response(db, complaint.id)
    return schemas.ComplaintOut.model_validate(refreshed)


@router.post("/{complaint_code}/find-duplicates")
def find_duplicates_endpoint(
    complaint_code: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        require_roles(models.Role.ADMIN.value, models.Role.FIELD_OFFICER.value)
    ),
):
    from ..ai.duplicate import find_duplicates

    complaint = db.query(models.Complaint).filter(models.Complaint.complaint_code == complaint_code).first()
    if not complaint:
        raise HTTPException(404, "Complaint not found")
    candidates = [
        {
            "id": c.id,
            "complaint_code": c.complaint_code,
            "raw_text": c.raw_text,
            "category": c.category,
            "latitude": c.latitude,
            "longitude": c.longitude,
            "civic_issue_id": c.civic_issue_id,
        }
        for c in db.query(models.Complaint).filter(models.Complaint.id != complaint.id).all()
        if c.civic_issue_id is not None
    ]
    result = find_duplicates(
        complaint.raw_text,
        complaint.category,
        complaint.latitude,
        complaint.longitude,
        candidates,
    )
    return {
        "is_duplicate": result.is_duplicate,
        "best_match": vars(result.best_match) if result.best_match else None,
        "all_matches": [vars(match) for match in result.all_matches],
    }
