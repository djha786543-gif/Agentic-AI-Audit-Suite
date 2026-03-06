@echo off
setlocal

set REPO_ROOT=%~dp0
cd /d "%REPO_ROOT%"

echo ==========================================
echo         ACAP AUTO SYNC LAUNCHER
echo ==========================================
echo.
echo Choose sync mode:
echo.
echo   1. Safe auto-sync (auto-pull only)
echo   2. Auto-sync after every change (auto-commit + auto-push)
echo   3. One-shot sync now (single run)
echo.

set "SYNC_MODE="
set /p SYNC_MODE=Enter 1, 2, or 3 and press Enter: 

if "%SYNC_MODE%"=="1" goto :MODE_SAFE
if "%SYNC_MODE%"=="2" goto :MODE_AUTOPUSH
if "%SYNC_MODE%"=="3" goto :MODE_ONCE

echo Invalid option. Starting safe mode by default.
goto :MODE_SAFE

:MODE_SAFE
echo.
echo Starting SAFE mode (auto-pull only)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%REPO_ROOT%auto_sync.ps1" -IntervalSec 20
goto :DONE

:MODE_AUTOPUSH
echo.
echo Starting AUTO-PUSH mode (sync after every change)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%REPO_ROOT%auto_sync.ps1" -IntervalSec 20 -AutoPush
goto :DONE

:MODE_ONCE
echo.
echo Running one-shot sync now...
powershell -NoProfile -ExecutionPolicy Bypass -File "%REPO_ROOT%auto_sync.ps1" -Once
goto :DONE

:DONE
endlocal
