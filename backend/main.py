from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text
from .database import Base, engine, SessionLocal
from .config import CORS_ORIGINS, UPLOAD_DIR
from . import models
from .routers import complaints, civic_issues, dashboard, sla, auth
from .seed import seed_if_empty

app = FastAPI(
    title="CivicFix API",
    description="AI Citizen Grievance Triage, Deduplication & Accountability -- classification, location extraction, duplicate detection, explainable priority scoring, and an admin SLA work queue.",
    version="1.0.0",
)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.include_router(complaints.router)
app.include_router(civic_issues.router)
app.include_router(dashboard.router)
app.include_router(sla.router)
app.include_router(auth.router)

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


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    ensure_auth_schema()
    db = SessionLocal()
    try:
        seed_if_empty(db)
        from .seed import ensure_demo_admin
        ensure_demo_admin(db)
    finally:
        db.close()

@app.get("/")
def root():
    return {"service": "CivicFix API", "status": "operational", "docs": "/docs"}

@app.get("/health")
def health():
    return {"status": "ok"}
