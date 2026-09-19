from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from . import models, sla_utils
from .data.gazetteer import GAZETTEER
from .ai.pipeline import run_triage, location_importance_of
from .ai.priority import compute_priority
from .security import hash_password


def seed_if_empty(db: Session):
    if db.query(models.Location).first() is not None:
        return
    _seed_gazetteer(db); _seed_users(db); db.commit(); _seed_complaints(db); db.commit()


def _seed_gazetteer(db: Session):
    for entry in GAZETTEER:
        db.add(models.Location(name=entry["name"], aliases=entry["aliases"], area_type=entry["area_type"], latitude=entry["latitude"], longitude=entry["longitude"], importance_weight=entry["importance_weight"], is_gazetteer=True))

DEMO_ADMINS = [
    ("Priyanka Deshmukh", "Roads & Infrastructure Dept."),
    ("Arjun Kulkarni", "Sanitation Dept."),
    ("Sameer Joshi", "Electrical Maintenance Dept."),
    ("Neha Patil", "Water & Drainage Dept."),
]


def _seed_users(db: Session):
    for name, dept in DEMO_ADMINS:
        db.add(models.User(name=name, role=models.Role.ADMIN.value, department=dept))
    db.add(models.User(name="Ward Control Room", role=models.Role.ADMIN.value, department="Control Room"))


def _hours_ago(h: float) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=h)


def _submit(db: Session, text: str, citizen: str, hours_ago: float) -> models.Complaint:
    citizen_user = db.query(models.User).filter(models.User.name == citizen, models.User.role == models.Role.CITIZEN.value).first()
    if not citizen_user:
        citizen_user = models.User(name=citizen, role=models.Role.CITIZEN.value); db.add(citizen_user); db.flush()
    complaint = models.Complaint(citizen_id=citizen_user.id, raw_text=text); db.add(complaint); db.flush()
    triage = run_triage(db, complaint); issue = triage["issue"]
    submitted_at = _hours_ago(hours_ago); complaint.created_at = submitted_at
    issue_opened = issue.created_at if issue.created_at.tzinfo else issue.created_at.replace(tzinfo=timezone.utc)
    if issue.complaint_count == 1 or issue_opened > submitted_at:
        issue.created_at = submitted_at if submitted_at < issue_opened else issue.created_at
    merged = db.query(models.Complaint).filter(models.Complaint.civic_issue_id == issue.id).all()
    max_severity = max((c.severity_hint or 2) for c in merged)
    priority = compute_priority(severity_hint=max_severity, complaint_count=issue.complaint_count, location_importance=location_importance_of(issue), created_at=issue.created_at, category=issue.category, has_verified_image_evidence=False)
    issue.priority_score = priority.total; issue.priority_band = priority.band; issue.priority_breakdown = priority.as_list()
    sla_utils.upsert_sla(db, issue)
    for h in issue.status_history: h.changed_at = issue.created_at
    db.flush(); return complaint


def _transition(db: Session, issue: models.CivicIssue, to_status: str, changed_by: str, note: str, hours_after_open: float = 1.0):
    old = issue.status; issue.status = to_status
    if to_status != models.IssueStatus.OPEN.value: issue.assigned_to = changed_by
    when = issue.created_at + timedelta(hours=hours_after_open)
    db.add(models.StatusHistory(civic_issue_id=issue.id, from_status=old, to_status=to_status, changed_by=changed_by, note=note, changed_at=when))
    if to_status == models.IssueStatus.RESOLVED.value:
        issue.resolved_at = when
        if issue.sla_record:
            issue.sla_record.resolved_at = when; sla_utils.recompute_state(issue.sla_record)


def _seed_complaints(db: Session):
    _submit(db, "Large pothole near Gate 2, several bikes almost fell.", "Rohan Mehta", 50)
    _submit(db, "Dangerous road hole outside Gate 2, very risky at night, please fix urgently.", "Ananya Rao", 46)
    _submit(db, "Huge pothole at the college main entrance near gate 2, cars are swerving to avoid it.", "Vikram Singh", 40)

    c1 = _submit(db, "Garbage has not been collected for a week near Shivaji Market, smells terrible.", "Kavya Nair", 70)
    _submit(db, "Overflowing trash bin near the market is attracting stray dogs, urgent cleanup needed.", "Farhan Sheikh", 65)
    issue = c1.civic_issue
    _transition(db, issue, models.IssueStatus.ASSIGNED.value, "Arjun Kulkarni", "Assigned to sanitation crew.", 3)
    _transition(db, issue, models.IssueStatus.IN_PROGRESS.value, "Arjun Kulkarni", "Cleanup crew dispatched.", 20)

    c2 = _submit(db, "Streetlight outside Gate 3 has been off for ten days, feels unsafe walking back to hostel at night.", "Ishaan Bhatt", 120)
    _transition(db, c2.civic_issue, models.IssueStatus.ASSIGNED.value, "Sameer Joshi", "Assigned to electrical maintenance.", 4)

    c3 = _submit(db, "Drain near Gate 2 is overflowing with dirty water after the rain, blocking the footpath.", "Meera Iyer", 30)
    _submit(db, "Open drain outside Gate 2 is flooding the road, sewage smell is unbearable.", "Devansh Rao", 26)
    _transition(db, c3.civic_issue, models.IssueStatus.ASSIGNED.value, "Neha Patil", "Assigned to drainage team, tanker requested.", 6)

    c4 = _submit(db, "Footpath tiles near the community park are broken and uneven, tripping hazard for elderly residents.", "Sanjana Ghosh", 96)
    _transition(db, c4.civic_issue, models.IssueStatus.ASSIGNED.value, "Priyanka Deshmukh", "Assigned to roads crew.", 5)
    _transition(db, c4.civic_issue, models.IssueStatus.IN_PROGRESS.value, "Priyanka Deshmukh", "Repair work started.", 30)
    _transition(db, c4.civic_issue, models.IssueStatus.RESOLVED.value, "Priyanka Deshmukh", "Footpath tiles relaid and inspected.", 60)

    c5 = _submit(db, "Streetlight near the underpass on Sinhagad Road is flickering badly every night.", "Tanmay Kulkarni", 80)
    _transition(db, c5.civic_issue, models.IssueStatus.ASSIGNED.value, "Sameer Joshi", "Electrician assigned.", 4)
    _transition(db, c5.civic_issue, models.IssueStatus.RESOLVED.value, "Sameer Joshi", "Faulty ballast replaced.", 40)

    _submit(db, "Minor pothole forming near the parking lot, not urgent but worth patching soon.", "Aditi Verma", 4)
    _submit(db, "No water supply in Green Valley Society since this morning.", "Rahul Deshpande", 6)
    _submit(db, "Plastic waste scattered near the community park entrance after the weekend market.", "Simran Kaur", 3)
    _submit(db, "Guard rail on the Ring Road flyover is bent after a minor accident last night.", "Om Prakash", 10)
    _submit(db, "Manhole cover is missing near the Ward Roundabout, quite dangerous for two-wheelers.", "Zoya Ahmed", 8)
    _submit(db, "Streetlight near Hanuman Temple Lane is not working, area is very dark at night.", "Yash Trivedi", 15)
    _submit(db, "Water pipeline near Railway Station Road is leaking heavily, wasting a lot of water.", "Pooja Reddy", 12)
    _submit(db, "Garbage bin near the bus stop is broken and trash is spilling onto the road.", "Karan Malhotra", 18)
    _submit(db, "Deep pothole near the Sinhagad Road Junction is damaging vehicle tyres.", "Nikita Shah", 5)
    _submit(db, "Drain near the Riverside Footbridge is choked, water pooling on the walkway.", "Aakash Bansal", 22)


def ensure_demo_admin(db: Session):
    """Create one local admin account for the prototype when it is missing."""
    email = "admin@civicfix.local"
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        user = db.query(models.User).filter(
            models.User.name == "Ward Control Room",
            models.User.role == models.Role.ADMIN.value,
        ).first()
    if user:
        user.email = email
        user.password_hash = user.password_hash or hash_password("Admin@12345")
        user.role = models.Role.ADMIN.value
        user.department = user.department or "Control Room"
        db.commit()
        return

    db.add(
        models.User(
            name="Ward Control Room",
            email=email,
            phone=None,
            role=models.Role.ADMIN.value,
            department="Control Room",
            password_hash=hash_password("Admin@12345"),
        )
    )
    db.commit()
