@echo off
title ACAP UAT Portal Launcher
color 0b
echo ==========================================
echo        ACAP UAT PORTAL LAUNCHER
echo ==========================================
echo.

set REPO_ROOT=%~dp0
cd /d "%REPO_ROOT%"

echo Starting ACAP local API in a new window...
start "ACAP Local API" powershell -NoProfile -ExecutionPolicy Bypass -File "%REPO_ROOT%run_local.ps1" -Port 8000

set "PORT_FILE=%REPO_ROOT%uat_reports\local_api_port.txt"
set "ACTIVE_PORT=8000"

echo Waiting for API startup and port detection...
for /l %%i in (1,1,30) do (
	if exist "%PORT_FILE%" (
		set /p ACTIVE_PORT=<"%PORT_FILE%"
		goto :port_found
	)
	timeout /t 1 /nobreak > nul
)

:port_found
echo Using port %ACTIVE_PORT%

powershell -NoProfile -Command "for ($i=0; $i -lt 40; $i++) { try { $r = Invoke-WebRequest -Uri ('http://127.0.0.1:' + $env:ACTIVE_PORT + '/api/v1/health') -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } } catch {}; Start-Sleep -Seconds 1 }; exit 0"

echo Opening UAT Portal...
start http://127.0.0.1:%ACTIVE_PORT%/uat.html

echo.
echo ------------------------------------------
echo UAT Portal: http://127.0.0.1:%ACTIVE_PORT%/uat.html
echo API Docs:   http://127.0.0.1:%ACTIVE_PORT%/docs
echo Login:      admin / Audit123!
echo ------------------------------------------
echo You can now run UAT directly from the portal.
echo.
pause
