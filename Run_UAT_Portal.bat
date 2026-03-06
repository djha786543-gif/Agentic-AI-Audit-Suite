@echo off
setlocal
title ACAP UAT Portal Launcher
color 0b
echo ==========================================
echo        ACAP UAT PORTAL LAUNCHER
echo ==========================================
echo.
echo Launcher file: %~f0
echo Launcher version: 2026-03-06.3
echo.

set REPO_ROOT=%~dp0
cd /d "%REPO_ROOT%"

set "ACTIVE_PORT=8000"

echo Starting ACAP local API in a new window...
start "ACAP Local API" powershell -NoProfile -ExecutionPolicy Bypass -File "%REPO_ROOT%run_local.ps1" -Port 8000 -NoReload

echo Waiting for API startup and active port discovery...
for /f %%p in ('powershell -NoProfile -Command "$ports = 8000..8050; for ($i = 0; $i -lt 40; $i++) { foreach ($p in $ports) { try { $r = Invoke-WebRequest -Uri ('http://127.0.0.1:' + $p + '/api/v1/health') -UseBasicParsing -TimeoutSec 1; if ($r.StatusCode -eq 200) { Write-Output $p; exit 0 } } catch {} }; Start-Sleep -Seconds 1 }; exit 1"') do set "ACTIVE_PORT=%%p"

if not defined ACTIVE_PORT set "ACTIVE_PORT=8000"

echo Using port %ACTIVE_PORT%

powershell -NoProfile -Command "for ($i=0; $i -lt 20; $i++) { try { $r = Invoke-WebRequest -Uri ('http://127.0.0.1:' + $env:ACTIVE_PORT + '/api/v1/health') -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } } catch {}; Start-Sleep -Seconds 1 }; exit 0"

echo Opening UAT Portal...
start "" "http://127.0.0.1:%ACTIVE_PORT%/uat.html"

echo.
echo ------------------------------------------
echo UAT Portal: http://127.0.0.1:%ACTIVE_PORT%/uat.html
echo API Docs:   http://127.0.0.1:%ACTIVE_PORT%/docs
echo Login:      admin / Audit123!
echo ------------------------------------------
echo You can now run UAT directly from the portal.
echo.
pause
endlocal
