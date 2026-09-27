# CivicFix deployment

## Backend — Render

Build command:

```bash
pip install -r backend/requirements.txt
```

Start command:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

Set:

- `DATABASE_URL` — Render PostgreSQL internal connection URL
- `CORS_ORIGINS` — include the Vercel frontend URL
- `AUTH_SECRET` — long random secret
- `PYTHON_VERSION=3.12.10`
- `UPLOAD_DIR=/opt/render/project/src/uploads`
- `MAX_ACTIVE_CASES_PER_WORKER=3`

Startup creates/updates the evidence and worker-routing fields needed by the current schema, provisions the 5 demo admins + 12 worker demo accounts, and refreshes worker capacity/queues.

## Frontend — Vercel

Root Directory: `frontend`

Build Command: `npm run build`

Output Directory: `dist`

Set:

```env
VITE_API_URL=https://YOUR-API.onrender.com
```

`vercel.json` contains the React Router SPA rewrite.

## Evidence storage

CivicFix stores initial complaint photos and completion evidence on disk. Render's default filesystem is ephemeral. Use a persistent disk or object-storage integration for production evidence retention.

## Citizen OTP

For local/demo testing, `OTP_DEMO_MODE=true` can be used. For real SMS verification, configure Twilio Verify server-side:

```env
OTP_PROVIDER=twilio
OTP_DEMO_MODE=false
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_VERIFY_SERVICE_SID=VA...
OTP_EXPIRY_MINUTES=5
OTP_COOLDOWN_SECONDS=30
OTP_MAX_ATTEMPTS=5
```

Never put SMS provider secrets in frontend code or commit them to Git.

## Three portals

- Citizen — OTP, multilingual text/voice, live-camera evidence, tracking and feedback.
- Admin — email/password, triage, routing/capacity view, assignment, SLA and evidence confirmation.
- Field Worker — email/password, exact-category queue, work status and live-camera completion evidence.

## Automatic worker routing

Six categories are each provisioned with two workers. After AI classification, CivicFix routes only within the matching category. The default maximum active workload is three cases per worker.

If both workers are at capacity, the issue stays `OPEN` and remains in that category's queue. When a worker's active workload falls below the limit, the queue router assigns the next eligible issue automatically.

## Production checklist

- Rotate every demo password in `CIVICFIX_LOGIN_CREDENTIALS.txt`.
- Replace the generated `AUTH_SECRET` with a controlled production secret.
- Configure real OTP/Twilio credentials.
- Configure persistent/object storage for evidence images.
- Set the exact Vercel frontend URL in `CORS_ORIGINS`.
- Review worker capacity before launch.
- Do not commit `.env` or the credential file.
