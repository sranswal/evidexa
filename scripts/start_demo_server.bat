@echo off
REM EVIDEXA One-Click Demo Environment Launcher
echo =======================================================================
echo                 EVIDEXA LIVE DEMO ENVIRONMENT LAUNCHER
echo =======================================================================
echo.

cd /d "%~dp0\.."

echo [0/3] Checking port 8000 availability...
powershell -NoProfile -Command "$conn = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'Listen' }; if ($conn) { Write-Host 'Terminating conflicting process on port 8000 (PID ' $conn[0].OwningProcess ')...'; Stop-Process -Id $conn[0].OwningProcess -Force -ErrorAction SilentlyContinue; Start-Sleep -Seconds 1 }"

echo [1/3] Verifying and bootstrapping examiner user...
call .venv\Scripts\python.exe scripts\bootstrap_dev_user.py

echo [2/3] Seeding demo investigation scenarios...
call .venv\Scripts\python.exe scripts\seed_demo_investigation.py

echo [3/3] Starting Backend (FastAPI :8000) and Frontend (Vite :5173)...
echo.
echo =======================================================================
echo  Backend:  http://127.0.0.1:8000 (API Docs at /docs)
echo  Frontend: http://localhost:5173
echo  Login:    examiner@evidexa.local / Investigator2026!
echo =======================================================================
echo.

start "EVIDEXA Backend (FastAPI)" cmd /k ".venv\Scripts\python.exe -m uvicorn document_intelligence.main:app --host 127.0.0.1 --port 8000 --reload"
timeout /t 2 >nul
start "EVIDEXA Frontend (Vite)" cmd /k "npm --prefix frontend run dev"

echo Servers launched in separate windows!
echo Opening browser to http://localhost:5173 ...
timeout /t 3 >nul
start http://localhost:5173
