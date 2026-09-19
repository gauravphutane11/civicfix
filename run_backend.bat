@echo off
cd /d %~dp0
if not exist .venv (
  python -m venv .venv
)
call .venv\Scripts\activate
pip install -r backend\requirements.txt
python -m backend.reset_demo
uvicorn backend.main:app --reload --port 8000
