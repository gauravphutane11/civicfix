from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, field_validator


class RegisterRequest(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    password: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Name must contain at least 2 characters")
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or "." not in value.rsplit("@", 1)[-1]:
            raise ValueError("Enter a valid email address")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters")
        return value


class LoginRequest(BaseModel):
    email: str
    password: str


class CitizenOtpRequest(BaseModel):
    phone: str
    name: Optional[str] = None
    email: Optional[str] = None
    language: Optional[str] = None


class CitizenOtpVerifyRequest(BaseModel):
    phone: str
    otp: str


class CitizenOtpRequestResponse(BaseModel):
    message: str
    expires_in_seconds: int
    retry_after_seconds: int
    demo_otp: Optional[str] = None
    is_new_user: bool
    delivery_mode: str = "demo"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: Optional[str]
    phone: Optional[str]
    role: str
    department: Optional[str]
    service_category: Optional[str] = None
    availability_status: Optional[str] = None
    is_active: bool = True


class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserOut


class ComplaintCreate(BaseModel):
    raw_text: str
    citizen_name: Optional[str] = "Anonymous Citizen"
    citizen_phone: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    file_path: str
    content_type: Optional[str]
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    capture_mode: Optional[str] = None
    ai_tags: list = []
    ai_confidence: Optional[float] = None
    ai_notes: Optional[str] = None
    is_verified: bool = False


class DuplicateInfoOut(BaseModel):
    is_duplicate: bool
    matched_complaint_code: Optional[str] = None
    similarity: Optional[float] = None
    shared_terms: List[str] = []
    civic_issue_code: Optional[str] = None


class WorkReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    complaint_id: int
    civic_issue_id: int
    citizen_id: int
    officer_id: Optional[int]
    rating: int
    review: Optional[str]
    created_at: datetime


class WorkReviewCreate(BaseModel):
    rating: int
    review: Optional[str] = None

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, value: int) -> int:
        if value < 1 or value > 5:
            raise ValueError("Rating must be between 1 and 5.")
        return value

    @field_validator("review")
    @classmethod
    def validate_review(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if len(value) > 500:
            raise ValueError("Review must be 500 characters or fewer.")
        return value or None


class FieldWorkEvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    civic_issue_id: int
    officer_id: int
    file_path: str
    content_type: Optional[str]
    capture_mode: str = "live_camera"
    latitude: float
    longitude: float
    note: Optional[str]
    uploaded_at: datetime


class CompletionEvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    complaint_id: int
    civic_issue_id: int
    citizen_id: int
    file_path: str
    content_type: Optional[str]
    capture_mode: str = "live_camera"
    latitude: float
    longitude: float
    uploaded_at: datetime
    matched_field_evidence_id: Optional[int]
    visual_similarity: Optional[float]
    location_distance_meters: Optional[float]
    location_score: Optional[float]
    verification_score: Optional[float]
    verification_status: str
    verification_note: Optional[str]
    reviewed_by: Optional[str]
    reviewed_at: Optional[datetime]


class CompletionEvidenceDecision(BaseModel):
    approved: bool
    note: Optional[str] = None

    @field_validator("note")
    @classmethod
    def validate_note(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if len(value) > 500:
            raise ValueError("Decision note must be 500 characters or fewer.")
        return value or None


class CompletionEvidenceResponse(BaseModel):
    evidence: CompletionEvidenceOut
    issue_status: str
    admin_confirmation_pending: bool = False


class ComplaintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    complaint_code: str
    raw_text: str
    citizen_name: Optional[str] = None
    citizen_email: Optional[str] = None
    citizen_phone: Optional[str] = None
    category: Optional[str]
    category_confidence: Optional[float]
    category_terms: list = []
    severity_hint: Optional[int] = None
    location_text_raw: Optional[str]
    location_confidence: Optional[float] = None
    latitude: Optional[float]
    longitude: Optional[float]
    status: str
    civic_issue_id: Optional[int]
    created_at: datetime
    attachments: List[AttachmentOut] = []
    review: Optional[WorkReviewOut] = None
    completion_evidence: List[CompletionEvidenceOut] = []

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        if obj is not None and hasattr(obj, "citizen"):
            citizen = getattr(obj, "citizen", None)
            if citizen is not None:
                data = {
                    "id": obj.id,
                    "complaint_code": obj.complaint_code,
                    "raw_text": obj.raw_text,
                    "citizen_name": citizen.name,
                    "citizen_email": citizen.email,
                    "citizen_phone": citizen.phone,
                    "category": obj.category,
                    "category_confidence": obj.category_confidence,
                    "category_terms": obj.category_terms or [],
                    "severity_hint": obj.severity_hint,
                    "location_text_raw": obj.location_text_raw,
                    "location_confidence": obj.location_confidence,
                    "latitude": obj.latitude,
                    "longitude": obj.longitude,
                    "status": obj.status,
                    "civic_issue_id": obj.civic_issue_id,
                    "created_at": obj.created_at,
                    "attachments": getattr(obj, "attachments", []) or [],
                    "review": getattr(obj, "work_review", None),
                    "completion_evidence": getattr(obj, "completion_evidence", []) or [],
                }
                return super().model_validate(data, *args, **kwargs)
        return super().model_validate(obj, *args, **kwargs)


class ComplaintSubmitResponse(BaseModel):
    complaint: ComplaintOut
    civic_issue_code: str
    civic_issue_id: int
    priority_score: int
    priority_band: str
    priority_breakdown: list
    duplicate_info: DuplicateInfoOut
    location_matched: bool
    sla_due_at: Optional[datetime]
    sla_target_hours: Optional[int]
    historical_context: Optional[dict] = None
    ai_explanation: Optional[str] = None
    input_language: Optional[str] = None
    input_language_name: Optional[str] = None
    language_confidence: Optional[float] = None
    normalized_text: Optional[str] = None
    classification_method: Optional[str] = None
    department: Optional[str] = None
    assigned_to: Optional[str] = None
    assignment_source: Optional[str] = None
    assignment_note: Optional[str] = None


class StatusHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    from_status: Optional[str]
    to_status: str
    changed_by: Optional[str]
    note: Optional[str]
    changed_at: datetime


class SLAOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    target_hours: int
    due_at: datetime
    resolved_at: Optional[datetime]
    state: str


class CivicIssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    issue_code: str
    category: str
    representative_text: str
    location_text_raw: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    priority_score: int
    priority_band: str
    priority_breakdown: list = []
    status: str
    assigned_to: Optional[str]
    department: Optional[str]
    assigned_at: Optional[datetime] = None
    assignment_source: Optional[str] = None
    assignment_note: Optional[str] = None
    complaint_count: int
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime]
    complaints: List[ComplaintOut] = []
    field_work_evidence: List[FieldWorkEvidenceOut] = []
    completion_evidence: List[CompletionEvidenceOut] = []
    status_history: List[StatusHistoryOut] = []
    sla_record: Optional[SLAOut] = None


class CivicIssueSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    issue_code: str
    category: str
    representative_text: str
    location_text_raw: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    priority_score: int
    priority_band: str
    status: str
    department: Optional[str]
    assigned_to: Optional[str] = None
    assignment_source: Optional[str] = None
    assignment_note: Optional[str] = None
    complaint_count: int
    created_at: datetime
    sla_record: Optional[SLAOut] = None


class StatusUpdate(BaseModel):
    status: str
    changed_by: Optional[str] = "Admin"
    note: Optional[str] = None


class AssignmentUpdate(BaseModel):
    assigned_to: str
    department: Optional[str] = None
    changed_by: Optional[str] = "Admin"


class DashboardMetrics(BaseModel):
    total_complaints: int
    total_civic_issues: int
    open_issues: int
    critical_issues: int
    high_issues: int
    resolved_issues: int
    duplicates_consolidated: int
    sla_within: int
    sla_at_risk: int
    sla_breached: int
    sla_compliance_pct: float
    avg_resolution_hours: Optional[float]
    by_category: dict
    by_status: dict


class MapPoint(BaseModel):
    id: int
    issue_code: str
    category: str
    latitude: float
    longitude: float
    priority_band: str
    priority_score: int
    status: str
    complaint_count: int
    location_name: Optional[str]


class WorkerRosterOut(BaseModel):
    id: int
    name: str
    email: Optional[str]
    role: str
    service_category: Optional[str]
    department: Optional[str]
    availability_status: str
    is_active: bool
    active_cases: int
    queued_cases: int
    current_issue_codes: list[str] = []


class WorkerOverviewOut(BaseModel):
    worker: WorkerRosterOut
    category: str
    department: str
    max_active_cases: int
    category_open_cases: int
    category_active_cases: int
    category_resolved_cases: int
    sibling_workers: list[WorkerRosterOut] = []
