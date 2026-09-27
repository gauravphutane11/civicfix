"""Capacity-aware field-worker routing for CivicFix."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from . import models
from .config import MAX_ACTIVE_CASES_PER_WORKER
from .department_mapping import department_for_category, is_routable_category

ACTIVE_ISSUE_STATES = {
    models.IssueStatus.ASSIGNED.value,
    models.IssueStatus.IN_PROGRESS.value,
}
WORKER_AVAILABLE = "available"
WORKER_BUSY = "busy"
WORKER_AT_CAPACITY = "at_capacity"
WORKER_OFFLINE = "offline"


def _aware(value: Optional[datetime]) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def worker_case_count(db: Session, worker: models.User) -> int:
    return (
        db.query(models.CivicIssue)
        .filter(
            models.CivicIssue.status.in_(ACTIVE_ISSUE_STATES),
            or_(
                models.CivicIssue.assigned_to == worker.name,
                models.CivicIssue.assigned_to == worker.email,
            ),
        )
        .count()
    )


def queued_case_count(db: Session, category: str) -> int:
    return (
        db.query(models.CivicIssue)
        .filter(
            models.CivicIssue.category == category,
            models.CivicIssue.status == models.IssueStatus.OPEN.value,
            models.CivicIssue.assigned_to.is_(None),
        )
        .count()
    )


def refresh_worker_status(db: Session, worker: models.User) -> int:
    if not worker.is_active:
        worker.availability_status = WORKER_OFFLINE
        return 0

    active = worker_case_count(db, worker)
    if active <= 0:
        worker.availability_status = WORKER_AVAILABLE
    elif active >= MAX_ACTIVE_CASES_PER_WORKER:
        worker.availability_status = WORKER_AT_CAPACITY
    else:
        worker.availability_status = WORKER_BUSY
    return active


def list_workers(db: Session, category: Optional[str] = None) -> list[models.User]:
    query = (
        db.query(models.User)
        .filter(models.User.role == models.Role.FIELD_OFFICER.value)
        .filter(models.User.is_active.is_(True))
    )
    if category:
        query = query.filter(models.User.service_category == category)
    workers = query.order_by(models.User.service_category.asc(), models.User.id.asc()).all()
    for worker in workers:
        refresh_worker_status(db, worker)
    return workers


def choose_worker(db: Session, category: str) -> tuple[Optional[models.User], str]:
    if not is_routable_category(category):
        return None, "This category does not have an automated field-worker unit."

    workers = list_workers(db, category)
    if not workers:
        return None, "No active worker account is provisioned for this category."

    scored: list[tuple[int, int, datetime, models.User]] = []
    for worker in workers:
        active = worker_case_count(db, worker)
        last = _aware(worker.last_auto_assigned_at)
        if active < MAX_ACTIVE_CASES_PER_WORKER:
            # Available workers are preferred.  Within the same state, use the
            # smallest workload and oldest auto-assignment timestamp.
            availability_rank = 0 if active == 0 else 1
            scored.append((availability_rank, active, last, worker))

    if not scored:
        return None, (
            f"All workers in {department_for_category(category)} are at the configured "
            f"capacity of {MAX_ACTIVE_CASES_PER_WORKER} active case(s)."
        )

    scored.sort(key=lambda row: (row[0], row[1], row[2], row[3].id))
    return scored[0][3], "Worker selected by category + availability + workload."


def assign_issue_to_worker(
    db: Session,
    issue: models.CivicIssue,
    *,
    source: str = "AI Auto-Router",
) -> tuple[Optional[models.User], str]:
    """Assign a new/open issue to a worker if capacity exists.

    If all two workers are at capacity, the issue remains OPEN and unassigned so
    the admin can see an explicit queue condition instead of a fake assignment.
    """
    issue.department = department_for_category(issue.category)

    if issue.assigned_to:
        assigned = (
            db.query(models.User)
            .filter(models.User.role == models.Role.FIELD_OFFICER.value)
            .filter(
                or_(
                    models.User.name == issue.assigned_to,
                    models.User.email == issue.assigned_to,
                )
            )
            .first()
        )
        if assigned:
            refresh_worker_status(db, assigned)
        return assigned, "Issue already has a worker assignment."

    worker, reason = choose_worker(db, issue.category)
    if worker is None:
        issue.assignment_source = "auto_queued"
        issue.assignment_note = reason
        return None, reason

    now = datetime.now(timezone.utc)
    old_status = issue.status
    issue.assigned_to = worker.name
    issue.assigned_at = now
    issue.assignment_source = source
    issue.assignment_note = reason
    worker.last_auto_assigned_at = now

    if issue.status == models.IssueStatus.OPEN.value:
        issue.status = models.IssueStatus.ASSIGNED.value
        db.add(
            models.StatusHistory(
                civic_issue_id=issue.id,
                from_status=old_status,
                to_status=models.IssueStatus.ASSIGNED.value,
                changed_by=source,
                note=f"Automatically routed to {worker.name} · {issue.department}.",
            )
        )

    refresh_worker_status(db, worker)
    return worker, reason


def fill_queue_for_category(db: Session, category: str) -> int:
    """Use newly available capacity to clear OPEN/unassigned work."""
    if not is_routable_category(category):
        return 0

    max_open_issues = (
        db.query(models.CivicIssue)
        .filter(
            models.CivicIssue.category == category,
            models.CivicIssue.status == models.IssueStatus.OPEN.value,
            models.CivicIssue.assigned_to.is_(None),
        )
        .count()
    )
    if max_open_issues <= 0:
        return 0

    assigned_count = 0
    for _ in range(max_open_issues):
        worker, reason = choose_worker(db, category)
        if worker is None:
            break

        issue = (
            db.query(models.CivicIssue)
            .filter(
                models.CivicIssue.category == category,
                models.CivicIssue.status == models.IssueStatus.OPEN.value,
                models.CivicIssue.assigned_to.is_(None),
            )
            .order_by(
                models.CivicIssue.priority_score.desc(),
                models.CivicIssue.created_at.asc(),
            )
            .first()
        )
        if issue is None:
            break

        issue.department = department_for_category(category)
        issue.assigned_to = worker.name
        issue.assigned_at = datetime.now(timezone.utc)
        issue.assignment_source = "AI Queue Router"
        issue.assignment_note = reason
        old = issue.status
        issue.status = models.IssueStatus.ASSIGNED.value
        worker.last_auto_assigned_at = datetime.now(timezone.utc)
        db.add(
            models.StatusHistory(
                civic_issue_id=issue.id,
                from_status=old,
                to_status=issue.status,
                changed_by="AI Queue Router",
                note=f"Queued issue assigned to {worker.name} after capacity became available.",
            )
        )
        refresh_worker_status(db, worker)
        assigned_count += 1

    return assigned_count


def refresh_all_worker_statuses(db: Session) -> None:
    for worker in db.query(models.User).filter(
        models.User.role == models.Role.FIELD_OFFICER.value
    ).all():
        refresh_worker_status(db, worker)
