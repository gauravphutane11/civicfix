# CivicFix — AI Citizen Grievance Triage, Deduplication & Accountability

CivicFix is a hackathon-grade civic service prototype for PS-18. It turns citizen reports into structured municipal work items and closes the loop with automatic service-category routing, field-worker evidence, citizen verification and an auditable admin workflow.

## End-to-end flow

Citizen OTP → multilingual text/voice complaint → live camera photo + GPS → civic classification → location intelligence → image relevance → duplicate detection → civic issue cluster → explainable priority → SLA → automatic category-aware worker routing → field worker work → live geotagged completion photo → optional citizen live after-work photo → evidence consistency check → admin confirmation/rejection → citizen rating/review.

## Technology stack

### Frontend

- React 18.3.1 — citizen, admin and field-worker interfaces.
- TypeScript 5.7.2 — typed UI/API contracts.
- Vite 6.0.5 — development server and bundling.
- Tailwind CSS 3.4.17 + custom CSS — public-service UI and operations console.
- React Router 6.28.0 — route protection and navigation.
- Leaflet 1.9.4 + React-Leaflet 4.2.1 — admin/field spatial views.
- OpenStreetMap — map tiles without a Google Maps API key.

### Backend

- FastAPI 0.115.6 — REST API and workflow orchestration.
- SQLAlchemy 2.0.36 — relational data access.
- SQLite — local development database.
- PostgreSQL — deployment database through `DATABASE_URL`.
- Pydantic 2.10.3 — request/response validation.

### AI / computer vision

- Scikit-learn 1.5.2 — TF-IDF and Multinomial Naive Bayes models.
- Multilingual character n-gram model — native-script civic classification for validated supported Indian languages.
- Civic vocabulary + script/language detection — multilingual canonicalization without requiring citizen translation.
- TF-IDF cosine similarity + 250 m spatial gate — duplicate grouping.
- Explainable additive priority engine — severity, recurrence, location importance, age and public impact.
- Pillow + OpenCV — image validation, civic-relevance heuristics and completion-photo consistency.
- Haversine distance — geospatial evidence matching and proximity checks.

Voice capture uses browser SpeechRecognition / webkitSpeechRecognition. The browser performs speech-to-text; CivicFix's backend then processes the resulting text.

## Multilingual AI

The citizen UI offers 23 Indian-language choices. Backend complaint classification has strongest validated native-language coverage for English, Hindi, Marathi, Gujarati, Bengali, Tamil, Telugu, Kannada, Malayalam, Odia, Punjabi and Urdu.

Example:

`आमच्या रस्त्यावर खूप मोठा खड्डा आहे`

→ Marathi detection
→ native-script civic features
→ `pothole`
→ confidence + supporting terms

The original citizen text is preserved. CivicFix does not require the citizen to translate the complaint into English.

## Automatic worker network

CivicFix provisions exactly **12 field-worker accounts: two workers for each of six AI-routable categories**.

| AI category | Department |
|---|---|
| `pothole` | Pothole Response |
| `garbage` | Garbage & Waste |
| `streetlight` | Streetlight Maintenance |
| `drainage` | Drainage Response |
| `road_infrastructure` | Road Infrastructure |
| `water_supply` | Water Supply |

After AI classification, the router checks only the matching category. It prefers an available worker, then the lowest active workload, and enforces the configurable capacity limit (`MAX_ACTIVE_CASES_PER_WORKER`, default 3). When both workers are at capacity, the issue remains `OPEN` and enters that category queue. When capacity is released, the queue is automatically filled.

## Live-camera-only evidence

All civic evidence photos are captured from the live camera. The frontend uses `navigator.mediaDevices.getUserMedia()` through the reusable `LivePhotoCapture` component. There is no gallery/file-picker path.

The backend also requires `capture_mode=live_camera`, so manually submitted gallery/file evidence is rejected by the evidence endpoints.

Evidence paths:

- Citizen complaint: live camera + GPS.
- Field-worker completion: live camera + GPS.
- Citizen after-work confirmation: optional live camera + GPS.

## Resolution evidence

CivicFix stores the field-worker completion evidence and the optional citizen after-work evidence as separate records. When both exist, the system compares:

- visual similarity using lightweight OpenCV signals
- location distance between captures
- combined verification score

A sufficiently consistent pair becomes `verified` and can move the issue to `RESOLVED`; ambiguous evidence becomes `needs_review`. Admins can explicitly confirm or reject the evidence pair. The matcher is a decision-support signal, not forensic proof.

## Citizen feedback

After a case is resolved, the citizen may optionally submit a 1–5 star rating and written review. This is kept separate from evidence verification so satisfaction is not used as a proxy for proof of physical completion.

## Local setup

Run the backend from the project root so package-relative imports work correctly:

```bash
python -m venv .venv
# Windows PowerShell
.venv\\Scripts\\Activate.ps1
pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --reload --port 8000
```

Open a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend: `http://localhost:5173`
Backend: `http://127.0.0.1:8000`
Swagger: `http://127.0.0.1:8000/docs`

## Routes

- `/` — citizen landing page
- `/login` — citizen OTP / admin email-password / service-worker email-password portal
- `/report` — citizen complaint intake
- `/complaints` — citizen complaint history, optional after-work evidence and feedback
- `/track` — public complaint tracking
- `/admin` — municipal operations console
- `/field-officer` — category-specific field-service work queue

## Credentials

`CIVICFIX_LOGIN_CREDENTIALS.txt` contains the complete hackathon/demo credentials for 5 admin accounts and 12 workers. It is intentionally ignored by Git. Rotate all passwords and remove demo credentials before real production use.

## Data and responsible AI

The project uses curated/synthetic campus-style demo data plus a processed historical NYC 311 reference file. The historical data is contextual reference data, not a live municipal feed.

Duplicate detection, image relevance and completion-image matching are probabilistic/heuristic decision-support signals. Human review remains part of the workflow.

## Deployment

Backend: Render + PostgreSQL.
Frontend: Vercel.
Persistent image storage requires a persistent disk/object store in production because local Render filesystem storage is ephemeral.

See `DEPLOYMENT.md` and `FIELD_OFFICER_SETUP.md` for deployment and worker routing details.
