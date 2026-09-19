import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, DateTime, ForeignKey, Text, Boolean, JSON
from sqlalchemy.orm import relationship
from .database import Base


def _now():
    return datetime.now(timezone.utc)


def short_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


class Role(str, enum.Enum):
    CITIZEN = "citizen"
    ADMIN = "admin"
    FIELD_OFFICER = "field_officer"


class IssueCategory(str, enum.Enum):
    POTHOLE = "pothole"
    GARBAGE = "garbage"
    STREETLIGHT = "streetlight"
    DRAINAGE = "drainage"
    ROAD_INFRASTRUCTURE = "road_infrastructure"
    WATER_SUPPLY = "water_supply"
    OTHER = "other"


class ComplaintStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    TRIAGED = "triaged"
    MERGED = "merged"


class IssueStatus(str, enum.Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class PriorityBand(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=True)
    password_hash = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    role = Column(String, default=Role.CITIZEN.value, nullable=False)
    department = Column(String, nullable=True)
    created_at = Column(DateTime, default=_now)
    complaints = relationship("Complaint", back_populates="citizen")


class Location(Base):
    __tablename__ = "locations"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    aliases = Column(JSON, default=list)
    area_type = Column(String, nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    importance_weight = Column(Integer, default=10)
    is_gazetteer = Column(Boolean, default=True)
    complaints = relationship("Complaint", back_populates="location")
    civic_issues = relationship("CivicIssue", back_populates="location")


class CivicIssue(Base):
    __tablename__ = "civic_issues"
    id = Column(Integer, primary_key=True)
    issue_code = Column(String, unique=True, default=lambda: short_id("CI"))
    category = Column(String, nullable=False)
    representative_text = Column(Text, nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    location_text_raw = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    priority_score = Column(Integer, default=0)
    priority_band = Column(String, default=PriorityBand.LOW.value)
    priority_breakdown = Column(JSON, default=list)
    status = Column(String, default=IssueStatus.OPEN.value)
    assigned_to = Column(String, nullable=True)
    department = Column(String, nullable=True)
    complaint_count = Column(Integer, default=1)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)
    resolved_at = Column(DateTime, nullable=True)
    location = relationship("Location", back_populates="civic_issues")
    complaints = relationship("Complaint", back_populates="civic_issue")
    status_history = relationship("StatusHistory", back_populates="civic_issue", cascade="all, delete-orphan")
    sla_record = relationship("SLARecord", back_populates="civic_issue", uselist=False, cascade="all, delete-orphan")
    duplicate_links = relationship("DuplicateLink", back_populates="civic_issue", cascade="all, delete-orphan")


class Complaint(Base):
    __tablename__ = "complaints"
    id = Column(Integer, primary_key=True)
    complaint_code = Column(String, unique=True, default=lambda: short_id("CF"))
    citizen_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    raw_text = Column(Text, nullable=False)
    category = Column(String, nullable=True)
    category_confidence = Column(Float, nullable=True)
    category_terms = Column(JSON, default=list)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    location_text_raw = Column(String, nullable=True)
    location_confidence = Column(Float, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    severity_hint = Column(Integer, default=2)
    civic_issue_id = Column(Integer, ForeignKey("civic_issues.id"), nullable=True)
    status = Column(String, default=ComplaintStatus.SUBMITTED.value)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)
    citizen = relationship("User", back_populates="complaints")
    location = relationship("Location", back_populates="complaints")
    civic_issue = relationship("CivicIssue", back_populates="complaints")
    attachments = relationship("Attachment", back_populates="complaint", cascade="all, delete-orphan")


class Attachment(Base):
    __tablename__ = "attachments"
    id = Column(Integer, primary_key=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False)
    file_path = Column(String, nullable=False)
    content_type = Column(String, nullable=True)
    uploaded_at = Column(DateTime, default=_now)
    ai_tags = Column(JSON, default=list)
    ai_confidence = Column(Float, nullable=True)
    ai_notes = Column(String, nullable=True)
    is_verified = Column(Boolean, default=False)
    complaint = relationship("Complaint", back_populates="attachments")


class DuplicateLink(Base):
    __tablename__ = "duplicate_links"
    id = Column(Integer, primary_key=True)
    civic_issue_id = Column(Integer, ForeignKey("civic_issues.id"), nullable=False)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=False)
    matched_against_complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=True)
    similarity = Column(Float, nullable=False)
    reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=_now)
    civic_issue = relationship("CivicIssue", back_populates="duplicate_links")


class StatusHistory(Base):
    __tablename__ = "status_history"
    id = Column(Integer, primary_key=True)
    civic_issue_id = Column(Integer, ForeignKey("civic_issues.id"), nullable=False)
    from_status = Column(String, nullable=True)
    to_status = Column(String, nullable=False)
    changed_by = Column(String, nullable=True)
    note = Column(String, nullable=True)
    changed_at = Column(DateTime, default=_now)
    civic_issue = relationship("CivicIssue", back_populates="status_history")


class SLARecord(Base):
    __tablename__ = "sla_records"
    id = Column(Integer, primary_key=True)
    civic_issue_id = Column(Integer, ForeignKey("civic_issues.id"), unique=True, nullable=False)
    target_hours = Column(Integer, nullable=False)
    due_at = Column(DateTime, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    state = Column(String, default="within_sla")
    civic_issue = relationship("CivicIssue", back_populates="sla_record")
