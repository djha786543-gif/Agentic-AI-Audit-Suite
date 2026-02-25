@echo off
title ACAP Master Launcher
color 0b
echo ==========================================
echo    ACAP INTEGRATED AUDIT SUITE STARTING
echo ==========================================

:: 1. Start the Backend (The Brain)
echo [1/3] Launching Secure Vault Engine...
start "ACAP_BACKEND" /min cmd /c "python -m uvicorn main:app --port 8002"

:: 2. Start the Watcher (The Guard)
echo [2/3] Activating Watcher Agent...
start "ACAP_WATCHER" /min cmd /c "python watcher_agent.py"

:: 3. Give the system 5 seconds to wake up
echo [3/3] Synchronizing Data Streams...
timeout /t 5 /nobreak > nul

:: 4. Open the polished Dashboard
echo Opening Dashboard...
start index.html

echo.
echo ------------------------------------------
echo SUCCESS: ACAP is now LIVE and PROTECTED.
echo ------------------------------------------
echo (You can close this window. Keep the minimized terminals running!)
pause
