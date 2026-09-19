import shutil
import uuid
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, Depends, Form, UploadFile, File, HTTPException
from sqlalchemy.orm import Session, joinedload
from .. import models, schemas
from ..database import get_db
from ..config import UPLOAD_DIR
from ..ai.pipeline import run_triage
from ..ai.image_analysis import analyze_image
from ..security import get_current_user, require_roles

router = APIRouter(prefix="/complaints", tags=["complaints"])
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/jpg"}
MAX_IMAGE_SIZE = 8 * 1024 * 1024


def _get_or_create_citizen(db: Session, name: Optional[str], phone: Optional[str]) -> models.User:
    name = (name or "Anonymous Citizen").strip() or "Anonymous Citizen"
    user = db.query(models.User).filter(models.User.name == name, models.User.role == models.Role.CITIZEN.value).first()
    if user:
        return user
    user = models.User(name=name, phone=phone, role=models.Role.CITIZEN.value)
    db.add(user); db.flush(); return user


def _save_upload(file: UploadFile) -> str:
    ext = Path(file.filename or "").suffix or ".jpg"
    fname = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / fname
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return str(dest)


@router.post("", response_model=schemas.ComplaintSubmitResponse)
def create_complaint(
    raw_text: str = Form(...),
    citizen_name: Optional[str] = Form(None),
    citizen_phone: Optional[str] = Form(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(models.Role.CITIZEN.value)),
):
    raw_text = raw_text.strip()
    if len(raw_text) < 8:
        raise HTTPException(400, "Please describe the issue in a bit more detail.")

    # Identity comes from the authenticated account, never from anonymous form fields.
    complaint = models.Complaint(
        citizen_id=current_user.id,
        raw_text=raw_text,
        latitude=latitude,
        longitude=longitude,
    )
    db.add(complaint)
    db.flush()
    triage = run_triage(db, complaint)

    if image.content_type not in ALLOWED_IMAGE_TYPES:
        db.rollback()
        raise HTTPException(400, f"Unsupported image type: {image.content_type}")

    image_bytes = image.file.read(MAX_IMAGE_SIZE + 1)
    if len(image_bytes) > MAX_IMAGE_SIZE:
        image.file.seek(0)
        db.rollback()
        raise HTTPException(400, "Image must be 8 MB or smaller")
    image.file.seek(0)

    saved_path = _save_upload(image)
    analysis = analyze_image(saved_path, complaint.category or "other")
    attachment = models.Attachment(
        complaint_id=complaint.id,
        file_path=saved_path,
        content_type=image.content_type,
        ai_tags=analysis.tags,
        ai_confidence=analysis.supporting_confidence,
        ai_notes=f"brightness={analysis.brightness}, edge_density={analysis.edge_density}, color_variance={analysis.color_variance}",
    )
    db.add(attachment)
    db.flush()

    db.commit()
    db.refresh(complaint)
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
    )


@router.get("", response_model=List[schemas.ComplaintOut])
def list_complaints(category: Optional[str] = None, status: Optional[str] = None, civic_issue_id: Optional[int] = None, db: Session = Depends(get_db), current_user: models.User = Depends(require_roles(models.Role.ADMIN.value, models.Role.FIELD_OFFICER.value))):
    q = db.query(models.Complaint).options(joinedload(models.Complaint.attachments), joinedload(models.Complaint.citizen))
    if category: q = q.filter(models.Complaint.category == category)
    if status: q = q.filter(models.Complaint.status == status)
    if civic_issue_id: q = q.filter(models.Complaint.civic_issue_id == civic_issue_id)
    return q.order_by(models.Complaint.created_at.desc()).all()


@router.get("/mine", response_model=List[schemas.ComplaintOut])
def list_my_complaints(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_roles(models.Role.CITIZEN.value)),
):
    return (
        db.query(models.Complaint)
        .options(joinedload(models.Complaint.attachments), joinedload(models.Complaint.citizen))
        .filter(models.Complaint.citizen_id == current_user.id)
        .order_by(models.Complaint.created_at.desc())
        .all()
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
def get_complaint(complaint_code: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    complaint = db.query(models.Complaint).options(joinedload(models.Complaint.attachments), joinedload(models.Complaint.citizen)).filter(models.Complaint.complaint_code == complaint_code).first()
    if not complaint:
        raise HTTPException(404, "Complaint not found")
    if current_user.role not in {models.Role.ADMIN.value, models.Role.FIELD_OFFICER.value} and complaint.citizen_id != current_user.id:
        raise HTTPException(403, "You can only view your own complaints")
    return complaint


@router.post("/{complaint_code}/analyze", response_model=schemas.ComplaintOut)
def reanalyze_complaint(complaint_code: str, db: Session = Depends(get_db), current_user: models.User = Depends(require_roles(models.Role.ADMIN.value, models.Role.FIELD_OFFICER.value))):
    complaint = db.query(models.Complaint).filter(models.Complaint.complaint_code == complaint_code).first()
    if not complaint: raise HTTPException(404, "Complaint not found")
    from ..ai.classifier import classifier
    from ..ai.location import extract_location
    result = classifier.classify(complaint.raw_text)
    complaint.category = result.category; complaint.category_confidence = result.confidence; complaint.category_terms = result.key_terms; complaint.severity_hint = result.severity_hint
    loc = extract_location(complaint.raw_text)
    if loc.matched:
        complaint.location_text_raw = loc.place_name; complaint.location_confidence = loc.confidence; complaint.latitude = loc.latitude; complaint.longitude = loc.longitude
    db.commit(); db.refresh(complaint); return complaint


@router.post("/{complaint_code}/find-duplicates")
def find_duplicates_endpoint(complaint_code: str, db: Session = Depends(get_db), current_user: models.User = Depends(require_roles(models.Role.ADMIN.value, models.Role.FIELD_OFFICER.value))):
    from ..ai.duplicate import find_duplicates
    complaint = db.query(models.Complaint).filter(models.Complaint.complaint_code == complaint_code).first()
    if not complaint: raise HTTPException(404, "Complaint not found")
    candidates = [
        {"id": c.id, "complaint_code": c.complaint_code, "raw_text": c.raw_text, "category": c.category,
         "latitude": c.latitude, "longitude": c.longitude, "civic_issue_id": c.civic_issue_id}
        for c in db.query(models.Complaint).filter(models.Complaint.id != complaint.id).all()
        if c.civic_issue_id is not None
    ]
    result = find_duplicates(complaint.raw_text, complaint.category, complaint.latitude, complaint.longitude, candidates)
    return {"is_duplicate": result.is_duplicate, "best_match": vars(result.best_match) if result.best_match else None, "all_matches": [vars(m) for m in result.all_matches]}
