# CivicFix Worker Network & Resolution Evidence

This phase provides a third authenticated portal for municipal field workers while preserving the citizen and admin flows.

## Roles

- **Citizen** — mobile-number OTP login, multilingual text/voice complaint intake, live-camera complaint evidence, tracking, optional after-work live-camera evidence, optional rating/review.
- **Admin** — email/password login, AI triage queue, worker capacity view, assignment override, SLA management, resolution evidence review, final confirmation/rejection.
- **Field Worker** — email/password login, category-specific queue, work progress and live-camera geotagged completion evidence.

## Six service categories

| AI category | Service department | Workers |
|---|---|---|
| `pothole` | Pothole Response | 2 |
| `garbage` | Garbage & Waste | 2 |
| `streetlight` | Streetlight Maintenance | 2 |
| `drainage` | Drainage Response | 2 |
| `road_infrastructure` | Road Infrastructure | 2 |
| `water_supply` | Water Supply | 2 |

CivicFix provisions **12 field-worker accounts automatically: exactly two active demo workers for each category**.

## Worker capacity and automatic routing

The AI classifier first identifies the complaint category. The routing service then:

1. Restricts the candidate worker pool to the exact matching category.
2. Prefers an available worker with no active case.
3. Otherwise chooses the matching worker with the lowest active workload.
4. Limits each worker to `MAX_ACTIVE_CASES_PER_WORKER` active cases (default: 3).
5. If both workers for the category are at capacity, leaves the issue `OPEN` and places it in that category's queue.
6. When capacity becomes available, the queue router automatically assigns the highest-priority oldest queued issue to the newly available worker.

Workers can see their own assigned cases and unassigned cases from their exact category only. They cannot see another category's operational queue.

## Demo accounts

All passwords are for hackathon/demo use only. See `CIVICFIX_LOGIN_CREDENTIALS.txt` for the complete list of 5 admins and 12 workers.

## Live-camera evidence policy

CivicFix uses **live camera capture only** for all civic evidence flows:

- Initial citizen complaint photo — live camera + GPS.
- Citizen after-work confirmation photo — live camera + GPS.
- Field-worker completion photo — live camera + GPS.

There is no gallery/file-picker path in the frontend. The browser uses `navigator.mediaDevices.getUserMedia()` and captures a frame to a Blob/File before sending it through `FormData`. The backend requires `capture_mode=live_camera` for all three evidence paths.

## Resolution evidence flow

1. Citizen submits a complaint.
2. AI classifies it into one of the six routed categories.
3. CivicFix automatically assigns an available worker from that exact category, or queues the issue when both workers are at capacity.
4. Worker starts the work.
5. Worker captures a live completion photo at the work site; GPS is stored.
6. Citizen may optionally capture a fresh after-work photo from the same location; GPS is stored.
7. CivicFix compares the worker and citizen evidence using lightweight visual signals and geographic proximity.
8. A sufficiently consistent pair becomes `verified` and can auto-resolve the issue; weaker evidence becomes `needs_review`.
9. Admin sees both photos, the visual similarity, distance, and combined evidence score and can explicitly **Confirm completion** or **Reject & review**.
10. A resolved case can receive a 1–5 star citizen rating and optional written review.

The photo matcher is an evidence consistency signal, not forensic proof. Human review remains part of the production workflow.
