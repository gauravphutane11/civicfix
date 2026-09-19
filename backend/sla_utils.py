from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from . import models
from .config import SLA_HOURS

AT_RISK_FRACTION = 0.75


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def upsert_sla(db: Session, issue: models.CivicIssue) -> models.SLARecord:
    target_hours = SLA_HOURS.get(issue.priority_band, SLA_HOURS["MEDIUM"])
    due_at = _aware(issue.created_at) + timedelta(hours=target_hours)
    record = issue.sla_record
    if record is None:
        record = db.query(models.SLARecord).filter(models.SLARecord.civic_issue_id == issue.id).first()
    if record is None:
        record = models.SLARecord(civic_issue_id=issue.id, target_hours=target_hours, due_at=due_at, state="within_sla")
        db.add(record)
    else:
        record.target_hours = target_hours
        record.due_at = due_at
        recompute_state(record)
    return record


def recompute_state(record: models.SLARecord) -> str:
    now = datetime.now(timezone.utc)
    due = _aware(record.due_at)
    if record.resolved_at is not None:
        resolved = _aware(record.resolved_at)
        record.state = "met" if resolved <= due else "breached"
        return record.state
    if now > due:
        record.state = "breached"
    else:
        opened_at = due - timedelta(hours=record.target_hours)
        window_seconds = (due - opened_at).total_seconds()
        elapsed_seconds = (now - opened_at).total_seconds()
        fraction = elapsed_seconds / window_seconds if window_seconds > 0 else 1
        record.state = "at_risk" if fraction >= AT_RISK_FRACTION else "within_sla"
    return record.state


def mark_resolved(record: models.SLARecord):
    record.resolved_at = datetime.now(timezone.utc)
    recompute_state(record)
