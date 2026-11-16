# EVIDEXA One-Click Demo Environment Launcher (PowerShell)
Write-Host "=======================================================================" -ForegroundColor Cyan
Write-Host "                EVIDEXA LIVE DEMO ENVIRONMENT LAUNCHER                 " -ForegroundColor Cyan
Write-Host "=======================================================================" -ForegroundColor Cyan
Write-Host ""

$RootPath = Resolve-Path "$PSScriptRoot\.."
Set-Location $RootPath

Write-Host "[1/3] Bootstrapping administrative examiner account..." -ForegroundColor Yellow
& "$RootPath\.venv\Scripts\python.exe" "$RootPath\scripts\bootstrap_dev_user.py"

Write-Host "[2/3] Seeding rich multi-case investigation scenarios..." -ForegroundColor Yellow
& "$RootPath\.venv\Scripts\python.exe" "$RootPath\scripts\seed_demo_investigation.py"

Write-Host "[3/3] Launching Backend & Frontend..." -ForegroundColor Green
Write-Host " Backend:  http://127.0.0.1:8000 (API Docs at /docs)" -ForegroundColor White
Write-Host " Frontend: http://localhost:5173" -ForegroundColor White
Write-Host " Login:    examiner@evidexa.local / Investigator2026!" -ForegroundColor White
Write-Host "=======================================================================" -ForegroundColor Cyan

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$RootPath'; & '$RootPath\.venv\Scripts\python.exe' -m uvicorn document_intelligence.main:app --host 127.0.0.1 --port 8000 --reload"
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$RootPath'; npm --prefix frontend run dev"

Start-Sleep -Seconds 3
Start-Process "http://localhost:5173"
Write-Host "[SUCCESS] Environment is running! Good luck with the evaluation panel!" -ForegroundColor Green
