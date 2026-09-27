@echo off
setlocal
cd /d %~dp0
if not exist .venv (
  python -m venv .venv
)
call .venv\Scripts\activate
python -m pip install -r backend\requirements.txt
python -m backend.reset_demo
for /f "delims=" %%i in ('python -c "import socket; port=8000; s=socket.socket(); s.bind(('0.0.0.0', port)); s.close(); print(port)" 2^>nul') do set BACKEND_PORT=%%i
if not defined BACKEND_PORT (
  for /f "delims=" %%i in ('python -c "import socket; port=8001; s=socket.socket(); s.bind(('0.0.0.0', port)); s.close(); print(port)" 2^>nul') do set BACKEND_PORT=%%i
)
if not defined BACKEND_PORT (
  set BACKEND_PORT=8002
)
echo Backend port: %BACKEND_PORT%
python -m uvicorn backend.main:app --host 0.0.0.0 --port %BACKEND_PORT%
endlocal
