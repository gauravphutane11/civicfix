from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from .. import models, schemas, sla_utils
from ..database import get_db
from ..security import get_current_user, require_roles


router = APIRouter(
    prefix="/civic-issues",
    tags=["civic-issues"],
)


VALID_TRANSITIONS = {
    models.IssueStatus.OPEN.value: {
        models.IssueStatus.ASSIGNED.value,
        models.IssueStatus.REJECTED.value,
    },
    models.IssueStatus.ASSIGNED.value: {
        models.IssueStatus.IN_PROGRESS.value,
        models.IssueStatus.OPEN.value,
    },
    models.IssueStatus.IN_PROGRESS.value: {
        models.IssueStatus.RESOLVED.value,
        models.IssueStatus.ASSIGNED.value,
    },
    models.IssueStatus.RESOLVED.value: set(),
    models.IssueStatus.REJECTED.value: set(),
}


def _touch_sla_states(issues, db: Session):
    """
    Recompute SLA states for the returned issues and persist
    any updated SLA state.
    """
    for issue in issues:
        if issue.sla_record:
            sla_utils.recompute_state(issue.sla_record)

    db.commit()


@router.get(
    "",
    response_model=List[schemas.CivicIssueSummary],
)
def list_civic_issues(
    q: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    priority_band: Optional[str] = None,
    min_score: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        require_roles(
            models.Role.ADMIN.value,
            models.Role.FIELD_OFFICER.value,
        )
    ),
):
    query = (
        db.query(models.CivicIssue)
        .options(
            joinedload(models.CivicIssue.sla_record)
        )
        .outerjoin(models.CivicIssue.complaints)
        .outerjoin(models.Complaint.citizen)
    )

    # Global search
    if q:
        term = f"%{q.strip()}%"

        query = query.filter(
            or_(
                models.CivicIssue.issue_code.ilike(term),
                models.CivicIssue.representative_text.ilike(term),
                models.CivicIssue.location_text_raw.ilike(term),
                models.Complaint.complaint_code.ilike(term),
                models.Complaint.raw_text.ilike(term),
                models.User.name.ilike(term),
                models.User.email.ilike(term),
                models.User.phone.ilike(term),
            )
        )

    # Filters
    if category:
        query = query.filter(
            models.CivicIssue.category == category
        )

    if status:
        query = query.filter(
            models.CivicIssue.status == status
        )

    if priority_band:
        query = query.filter(
            models.CivicIssue.priority_band == priority_band
        )

    if min_score is not None:
        query = query.filter(
            models.CivicIssue.priority_score >= min_score
        )

    # IMPORTANT:
    # Do NOT use query.distinct() here.
    #
    # PostgreSQL JSON columns do not provide the equality
    # operator required by SELECT DISTINCT.
    #
    # SQLAlchemy's ORM identity map will still prevent
    # duplicate CivicIssue objects from appearing in the
    # final entity result.
    issues = (
        query
        .order_by(
            models.CivicIssue.priority_score.desc(),
            models.CivicIssue.created_at.asc(),
        )
        .all()
    )

    _touch_sla_states(issues, db)

    return issues


@router.get(
    "/{issue_id}",
    response_model=schemas.CivicIssueOut,
)
def get_civic_issue(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    issue = (
        db.query(models.CivicIssue)
        .options(
            joinedload(
                models.CivicIssue.complaints
            ).joinedload(
                models.Complaint.attachments
            ),
            joinedload(
                models.CivicIssue.status_history
            ),
            joinedload(
                models.CivicIssue.sla_record
            ),
        )
        .filter(
            models.CivicIssue.id == issue_id
        )
        .first()
    )

    if not issue:
        raise HTTPException(
            status_code=404,
            detail="Civic issue not found",
        )

    # Citizens can only access cases associated
    # with their own submitted complaints.
    if current_user.role not in {
        models.Role.ADMIN.value,
        models.Role.FIELD_OFFICER.value,
    }:
        owns_issue = any(
            complaint.citizen_id == current_user.id
            for complaint in issue.complaints
        )

        if not owns_issue:
            raise HTTPException(
                status_code=403,
                detail=(
                    "You can only view civic cases "
                    "linked to your reports"
                ),
            )

    if issue.sla_record:
        sla_utils.recompute_state(
            issue.sla_record
        )

    db.commit()

    issue.status_history.sort(
        key=lambda history: history.changed_at
    )

    return issue


@router.patch(
    "/{issue_id}/status",
    response_model=schemas.CivicIssueOut,
)
def update_status(
    issue_id: int,
    payload: schemas.StatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        require_roles(
            models.Role.ADMIN.value,
            models.Role.FIELD_OFFICER.value,
        )
    ),
):
    issue = db.get(
        models.CivicIssue,
        issue_id,
    )

    if not issue:
        raise HTTPException(
            status_code=404,
            detail="Civic issue not found",
        )

    new_status = payload.status

    if new_status not in VALID_TRANSITIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown status '{new_status}'",
        )

    if (
        new_status != issue.status
        and new_status
        not in VALID_TRANSITIONS.get(
            issue.status,
            set(),
        )
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot move issue from "
                f"'{issue.status}' to "
                f"'{new_status}'."
            ),
        )

    old_status = issue.status
    issue.status = new_status

    db.add(
        models.StatusHistory(
            civic_issue_id=issue.id,
            from_status=old_status,
            to_status=new_status,
            changed_by=payload.changed_by,
            note=payload.note,
        )
    )

    if (
        new_status
        == models.IssueStatus.RESOLVED.value
    ):
        from datetime import datetime, timezone

        issue.resolved_at = datetime.now(
            timezone.utc
        )

        if issue.sla_record:
            sla_utils.mark_resolved(
                issue.sla_record
            )

    db.commit()
    db.refresh(issue)

    return get_civic_issue(
        issue_id,
        db,
        current_user,
    )


@router.patch(
    "/{issue_id}/assign",
    response_model=schemas.CivicIssueOut,
)
def assign_issue(
    issue_id: int,
    payload: schemas.AssignmentUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        require_roles(
            models.Role.ADMIN.value
        )
    ),
):
    issue = db.get(
        models.CivicIssue,
        issue_id,
    )

    if not issue:
        raise HTTPException(
            status_code=404,
            detail="Civic issue not found",
        )

    issue.assigned_to = payload.assigned_to
    issue.department = payload.department

    old_status = issue.status

    if (
        issue.status
        == models.IssueStatus.OPEN.value
    ):
        issue.status = (
            models.IssueStatus.ASSIGNED.value
        )

        db.add(
            models.StatusHistory(
                civic_issue_id=issue.id,
                from_status=old_status,
                to_status=(
                    models.IssueStatus.ASSIGNED.value
                ),
                changed_by=payload.changed_by,
                note=(
                    f"Assigned to "
                    f"{payload.assigned_to} "
                    f"({payload.department})"
                ),
            )
        )

    db.commit()
    db.refresh(issue)

    return get_civic_issue(
        issue_id,
        db,
        current_user,
    )