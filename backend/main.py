from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

from .database import Base, engine, SessionLocal
from .config import CORS_ORIGIN_REGEX, CORS_ORIGINS, UPLOAD_DIR
from . import models
from .routers import complaints, civic_issues, dashboard, sla, auth, field_officer
from .seed import seed_if_empty
from .department_mapping import department_for_category
from .worker_provisioning import provision_accounts, WORKER_ACCOUNTS
from .worker_routing import fill_queue_for_category, refresh_all_worker_statuses

app = FastAPI(
    title="CivicFix API",
    description=(
        "AI Citizen Grievance Triage, Deduplication & Accountability -- "
        "multilingual classification, location extraction, duplicate detection, "
        "explainable priority scoring, field-work routing, resolution evidence, "
        "citizen reviews and an admin SLA work queue."
    ),
    version="1.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.include_router(complaints.router)
app.include_router(civic_issues.router)
app.include_router(dashboard.router)
app.include_router(sla.router)
app.include_router(auth.router)
app.include_router(field_officer.router)


def ensure_auth_schema():
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    if "users" not in tables:
        return
    columns = {c["name"] for c in inspector.get_columns("users")}
    with engine.begin() as conn:
        if "email" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR"))
        if "password_hash" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR"))
        if "otp_hash" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN otp_hash VARCHAR"))
        if "otp_expires_at" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN otp_expires_at TIMESTAMP"))
        if "otp_attempts" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN otp_attempts INTEGER DEFAULT 0"))
        if "otp_requested_at" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN otp_requested_at TIMESTAMP"))
        if "otp_provider" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN otp_provider VARCHAR"))


def ensure_evidence_schema():
    """Add new evidence metadata columns to an existing pre-1.2 database."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    if "attachments" not in tables:
        return
    columns = {c["name"] for c in inspector.get_columns("attachments")}
    with engine.begin() as conn:
        if "latitude" not in columns:
            conn.execute(text("ALTER TABLE attachments ADD COLUMN latitude FLOAT"))
        if "longitude" not in columns:
            conn.execute(text("ALTER TABLE attachments ADD COLUMN longitude FLOAT"))
        if "capture_mode" not in columns:
            conn.execute(text("ALTER TABLE attachments ADD COLUMN capture_mode VARCHAR"))


def ensure_worker_schema():
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    with engine.begin() as conn:
        if "users" in tables:
            columns = {c["name"] for c in inspector.get_columns("users")}
            if "service_category" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN service_category VARCHAR"))
            if "availability_status" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN availability_status VARCHAR DEFAULT 'available'"))
            if "is_active" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT TRUE"))
            if "last_auto_assigned_at" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN last_auto_assigned_at TIMESTAMP"))
        if "civic_issues" in tables:
            columns = {c["name"] for c in inspector.get_columns("civic_issues")}
            if "assigned_at" not in columns:
                conn.execute(text("ALTER TABLE civic_issues ADD COLUMN assigned_at TIMESTAMP"))
            if "assignment_source" not in columns:
                conn.execute(text("ALTER TABLE civic_issues ADD COLUMN assignment_source VARCHAR"))
            if "assignment_note" not in columns:
                conn.execute(text("ALTER TABLE civic_issues ADD COLUMN assignment_note TEXT"))
        if "field_work_evidence" in tables:
            columns = {c["name"] for c in inspector.get_columns("field_work_evidence")}
            if "capture_mode" not in columns:
                conn.execute(text("ALTER TABLE field_work_evidence ADD COLUMN capture_mode VARCHAR DEFAULT 'live_camera'"))
        if "citizen_completion_evidence" in tables:
            columns = {c["name"] for c in inspector.get_columns("citizen_completion_evidence")}
            if "capture_mode" not in columns:
                conn.execute(text("ALTER TABLE citizen_completion_evidence ADD COLUMN capture_mode VARCHAR DEFAULT 'live_camera'"))


def ensure_civic_departments(db):
    legacy_departments = {
        "Roads & Infrastructure": "road_infrastructure",
        "Roads & Infrastructure Dept.": "road_infrastructure",
        "Sanitation": "garbage",
        "Sanitation Dept.": "garbage",
        "Street Lighting": "streetlight",
        "Electrical Maintenance Dept.": "streetlight",
        "Drainage": "drainage",
        "Water Supply": "water_supply",
        "Water & Drainage Dept.": "drainage",
        "General Works": "other",
    }
    legacy_worker_assignment = {
        "Priyanka Deshmukh": "Road Infrastructure Worker 01",
        "Arjun Kulkarni": "Garbage Worker 01",
        "Sameer Joshi": "Streetlight Worker 01",
        "Neha Patil": "Drainage Worker 01",
    }

    # Migrate legacy field-worker accounts to the new six-category roster.
    valid_emails = {account.email for account in WORKER_ACCOUNTS}
    for officer in db.query(models.User).filter(
        models.User.role == models.Role.FIELD_OFFICER.value
    ).all():
        if officer.email in valid_emails:
            continue
        category = legacy_departments.get(officer.department)
        if category in {"pothole", "road_infrastructure", "garbage", "streetlight", "drainage", "water_supply"}:
            officer.service_category = category
            officer.department = department_for_category(category)
        officer.is_active = False
        officer.availability_status = "offline"

    for issue in db.query(models.CivicIssue).all():
        if issue.category in {"pothole", "road_infrastructure", "garbage", "streetlight", "drainage", "water_supply"}:
            issue.department = department_for_category(issue.category)
        if issue.assigned_to in legacy_worker_assignment:
            issue.assigned_to = legacy_worker_assignment[issue.assigned_to]
            issue.assignment_source = issue.assignment_source or "Legacy assignment migrated"
            issue.assignment_note = issue.assignment_note or "Legacy field-officer assignment migrated to the current six-category roster."
        if issue.status in {
            models.IssueStatus.OPEN.value,
            models.IssueStatus.ASSIGNED.value,
            models.IssueStatus.IN_PROGRESS.value,
            models.IssueStatus.RESOLVED.value,
            models.IssueStatus.REJECTED.value,
        }:
            for complaint in issue.complaints:
                complaint.status = issue.status


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    ensure_auth_schema()
    ensure_evidence_schema()
    ensure_worker_schema()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_if_empty(db)
        provision_accounts(db)
        ensure_civic_departments(db)
        refresh_all_worker_statuses(db)
        for category in {a.service_category for a in WORKER_ACCOUNTS if a.service_category}:
            fill_queue_for_category(db, category)
        db.commit()
    finally:
        db.close()


@app.get("/")
def root():
    return {"service": "CivicFix API", "status": "operational", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}
