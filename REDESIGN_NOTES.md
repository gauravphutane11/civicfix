# CivicFix Command Center redesign

This version replaces the original blueprint/paper visual language with a modern civic-service UI:
- Citizen: simple report + complaint history workflow.
- Admin: command center with universal search, attention queue, SLA escalation, map, hotspot recurrence, workload view and case drawer.

## Admin search
The admin search field covers:
- civic issue ID
- complaint ID
- citizen name
- citizen email
- citizen phone
- issue description
- location

## New operational features
- Transparent attention score combining priority, SLA state, recurrence and queue state.
- Escalation lane for critical / at-risk / breached cases.
- Hotspot recurrence view by mapped location.
- Department workload view.
- Citizen profile inside every case drawer.
- Evidence verification toggle for admin review.
- Duplicate cluster view showing all citizen reports consolidated into a civic case.
- Decision trace showing AI category/location confidence and priority factor contributions.
- Search/filter/sort queue plus CSV export.
- Admin assignment with department selection and status notes.

## Backend additions
- `GET /civic-issues?q=...` universal admin search.
- `PATCH /complaints/attachments/{attachment_id}/verify` evidence verification.
- Complaint responses now expose citizen identity to authorized admin views.

## Run
Backend from project root:

```powershell
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd frontend
npm run dev
```
