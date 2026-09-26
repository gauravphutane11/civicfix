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
