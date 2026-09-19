from datetime import datetime
from typing import Optional, List
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


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: Optional[str]
    phone: Optional[str]
    role: str
    department: Optional[str]


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
    complaint_count: int
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime]
    complaints: List[ComplaintOut] = []
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
    complaint_count: int
    created_at: datetime
    sla_record: Optional[SLAOut] = None


class StatusUpdate(BaseModel):
    status: str
    changed_by: Optional[str] = "Admin"
    note: Optional[str] = None


class AssignmentUpdate(BaseModel):
    assigned_to: str
    department: str
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
