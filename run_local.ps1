param(
    [int]$Port = 8000,
    [switch]$SkipInstall,
    [switch]$NoReload
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

function Test-PortAvailable {
    param([int]$CandidatePort)

    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $CandidatePort)
    try {
        $listener.Start()
        return $true
    }
    catch {
        return $false
    }
    finally {
        if ($listener.Server -and $listener.Server.IsBound) {
            $listener.Stop()
        }
    }
}

function New-LocalVenv {
    param([string]$VenvPath)

    if (Get-Command py -ErrorAction SilentlyContinue) {
        Write-Host "Creating virtual environment with py..." -ForegroundColor Cyan
        & py -3.12 -m venv $VenvPath
        return
    }

    if (Get-Command python -ErrorAction SilentlyContinue) {
        Write-Host "Creating virtual environment with python..." -ForegroundColor Cyan
        & python -m venv $VenvPath
        return
    }

    throw "Python launcher not found. Install Python 3.12+ and re-run this script."
}

Write-Host "== ACAP Local API Runner ==" -ForegroundColor Green

$venvPath = Join-Path $RepoRoot ".venv"
$pythonExe = Join-Path $venvPath "Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    New-LocalVenv -VenvPath $venvPath
}

if (-not (Test-Path $pythonExe)) {
    throw "Virtual environment creation failed. Expected: $pythonExe"
}

if (-not $SkipInstall) {
    Write-Host "Installing dependencies from requirements.txt..." -ForegroundColor Cyan
    & $pythonExe -m pip install --upgrade pip
    & $pythonExe -m pip install -r requirements.txt
}

$selectedPort = $Port
while (-not (Test-PortAvailable -CandidatePort $selectedPort)) {
    $selectedPort++
}

if ($selectedPort -ne $Port) {
    Write-Host "Port $Port is unavailable. Using port $selectedPort instead." -ForegroundColor Yellow
}

$reportsDir = Join-Path $RepoRoot "uat_reports"
if (-not (Test-Path $reportsDir)) {
    New-Item -ItemType Directory -Path $reportsDir | Out-Null
}
$portFile = Join-Path $reportsDir "local_api_port.txt"
Set-Content -Path $portFile -Value "$selectedPort" -Encoding UTF8

$uvicornArgs = @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "$selectedPort")
if (-not $NoReload) {
    $uvicornArgs += "--reload"
}

Write-Host "Starting API at http://127.0.0.1:$selectedPort" -ForegroundColor Green
Write-Host "Docs: http://127.0.0.1:$selectedPort/docs" -ForegroundColor Green
Write-Host "Demo login: admin / Audit123!" -ForegroundColor Green

& $pythonExe @uvicornArgs
