# CivicFix — AI Citizen Grievance Triage, Deduplication & Accountability

CivicFix is a hackathon-grade prototype for **PS-18** of the Global SDG + AI Hackathon 2026. It turns fragmented civic complaints into deduplicated, explainable and SLA-trackable municipal work items.

## Product flow

Citizen report → AI classification → location extraction → duplicate detection → civic issue cluster → explainable priority → SLA → admin action → resolution.

## AI modules

1. **Complaint classification:** TF-IDF + Multinomial Naive Bayes over a compact hand-labelled corpus.
2. **Location extraction:** token-aware phrase extraction + exact/fuzzy alias matching against a curated Pune-style gazetteer.
3. **Duplicate detection:** domain synonym normalization + TF-IDF cosine similarity + spatial proximity weighting.
4. **Explainable priority:** transparent 100-point additive model using severity, recurrence, location importance, age and public impact.
5. **Image evidence:** deterministic Pillow-based brightness/edge/colour statistics. This is explicitly heuristic support, not a trained CNN.

## Repository

- `backend/` — FastAPI, SQLAlchemy, SQLite, AI pipeline, REST API, seed data.
- `frontend/` — React/Vite/TypeScript, Tailwind, Leaflet map, citizen + admin workflows.

## Local setup

### 1. Backend

```bash
cd backend
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS/Linux
# source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

The API exposes Swagger at `http://127.0.0.1:8000/docs`.

### 2. Frontend

Open a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

The Vite proxy forwards `/api/*` to the FastAPI server and `/uploads/*` to FastAPI.

## Main routes

- `/` — public CivicFix landing / explanation
- `/report` — citizen complaint intake + AI triage receipt (photo + location required)
- `/track` — complaint tracking
- `/admin` — municipal operations console

## Flagship demo scenario

The backend seeds a real AI-driven Gate 2 duplicate cluster:

- `Large pothole near Gate 2...`
- `Dangerous road hole outside Gate 2...`
- `Huge pothole at the college main entrance...`

These are processed by the actual pipeline and become one civic issue where similarity crosses the configured threshold.

## Environment

Copy `.env.example` to `.env` if you want custom settings. SQLite is the default local database.

## Responsible AI notes

- The system is a decision-support prototype, not an autonomous municipal decision-maker.
- Duplicate detection is probabilistic and should be reviewed by staff.
- Location is required at submission time; production deployments should still validate coordinate quality and user consent.
- Location text can be unresolved when a recognizable place cannot be matched; the UI surfaces that uncertainty.
- Priority factors are transparent and editable in code.
- Image analysis is intentionally labelled as heuristic supporting evidence rather than object detection.
- Input validation is explicit: reports require authenticated access, a clear image, and location evidence.

## Data

The prototype includes a 50,000-record historical reference sample derived from the public **NYC 311 Service Requests** dataset for category-level context. The bundled summary is limited to the 2019 sample used by this prototype and is not presented as live Pune data.

The map itself uses public OpenStreetMap tiles and the complaint location model uses a curated Pune-style gazetteer for deterministic demo mapping. Replace the demo gazetteer and historical reference with verified municipal datasets before real-world deployment.

## Validation performed in this handoff

- Python backend syntax compiled successfully.
- Classifier, location extractor and priority engine were executed directly.
- Demo database seed executed successfully.
- Seeded flagship Gate 2 pothole cluster produced one civic issue with 3 reports.
- Related Gate 2 drainage reports were also consolidated into one issue after tightening location extraction.
- FastAPI `/health`, `/dashboard/metrics`, `/dashboard/map`, and complaint submission were exercised with a local TestClient.
- Frontend TypeScript compilation passed in this handoff. If the existing local `node_modules` cache is incomplete, run `npm install` before `npm run dev` or `npm run build`.

## Authentication

Citizen reports now require a registered account and are linked to the authenticated citizen. The API uses signed JWT access tokens and salted PBKDF2 password hashes.

For the local prototype, a demo operations account is created automatically:

- Email: `admin@civicfix.local`
- Password: `Admin@12345`

Replace `AUTH_SECRET` in `.env` with a long random value before any non-local deployment.
