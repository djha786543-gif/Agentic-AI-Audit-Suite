@echo off
setlocal

set REPO_ROOT=%~dp0
cd /d "%REPO_ROOT%"

echo ==========================================
echo   ACAP AUTO SYNC (EVERY CHANGE MODE)
echo ==========================================
echo.
echo This mode auto-commits and auto-pushes local changes continuously.
echo Close this window to stop.
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%REPO_ROOT%auto_sync.ps1" -IntervalSec 20 -AutoPush

endlocal
