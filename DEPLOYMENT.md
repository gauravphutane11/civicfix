# CivicFix deployment

## Backend (Render)
Build: `pip install -r backend/requirements.txt`
Start: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
Set `DATABASE_URL`, `CORS_ORIGINS`, `AUTH_SECRET`, and `PYTHON_VERSION=3.12.10`.
Use the Render Postgres internal URL for `DATABASE_URL`.

## Frontend (Vercel)
Root Directory: `frontend`
Build Command: `npm run build`
Output Directory: `dist`
Set `VITE_API_URL=https://YOUR-API.onrender.com`.
`vercel.json` contains the SPA rewrite for React Router.

## Uploads
The app stores citizen images on local disk. Render's filesystem is ephemeral by default, so for persistent evidence images attach a Render persistent disk mounted at `/opt/render/project/src/uploads` (paid Render service).

## Real citizen OTP with Twilio Verify

CivicFix supports passwordless citizen login through Twilio Verify. The application starts an SMS verification and checks the 6-digit code server-side; no citizen password is required.

For local demo mode, keep `OTP_PROVIDER=auto` and `OTP_DEMO_MODE=true`. For production, configure these server-side secrets and disable demo mode:

```env
OTP_PROVIDER=twilio
OTP_DEMO_MODE=false
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_VERIFY_SERVICE_SID=VAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OTP_EXPIRY_MINUTES=5
OTP_COOLDOWN_SECONDS=30
OTP_MAX_ATTEMPTS=5
```

In the Twilio console, create a Verify Service and use its `VA...` Service SID. Store the account SID, auth token and Verify Service SID as protected environment variables; never put them in frontend code or commit them to Git.

Twilio Verify sends the verification SMS and performs the verification check. The selected CivicFix language is passed as the Verify locale when that locale is supported; the backend retries without an explicit locale when a template does not support the requested override.

> Twilio trial accounts can restrict verification delivery to verified recipient numbers. Upgrade the Twilio account before a public deployment.
