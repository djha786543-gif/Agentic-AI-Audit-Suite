@echo off
title ACAP Master Launcher
color 0b
echo ==========================================
echo    ACAP INTEGRATED AUDIT SUITE STARTING
echo ==========================================
echo.

:: Start all services via Docker Compose
echo [1/2] Starting Docker services (DB + Redis + API + Worker + Beat)...
docker compose up --build -d

:: Wait for API to become healthy
echo [2/2] Waiting for API to be ready...
timeout /t 15 /nobreak > nul

:: Open the dashboard
echo Opening Dashboard...
start http://localhost:8000

echo.
echo ------------------------------------------
echo SUCCESS: ACAP is now LIVE
echo   Dashboard:   http://localhost:8000
echo   API Docs:    http://localhost:8000/docs
echo   Login:       admin / Audit123!
echo ------------------------------------------
pause
