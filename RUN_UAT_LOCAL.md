# Run UAT Locally (Desktop)

This gives you a single-command local run.

## Quick Start

From the project folder:

```bash
python run_uat_local.py --scale deep
```

## One-Click Desktop UAT Portal (Windows)

Double-click:

```text
Run_UAT_Portal.bat
```

This starts the local API and opens:

```text
http://127.0.0.1:<active-port>/uat.html
```

Notes:

- The launcher auto-detects the active local port (8000 or next available)
- It waits for API health before opening the UAT portal URL

From that single page you can:

- Start UAT runs (small/medium/deep) without PowerShell commands
- Track run status live
- Refresh reports, compare runs, and execute Phase 2 patch workflow

Optional:

```bash
python run_uat_local.py --scale small --seed 42 --run-diff
```

## What the launcher does

- Creates `.venv` if needed
- Installs `requirements.txt` if needed
- Starts API server if not already running
- Runs `agents/uat_enterprise_agent.py`
- Executes complex Audit-of-AI scenarios (toxic access, self-approval, 3-way-match bypass, reconciliation mismatches)
- Saves reports in `uat_reports/`
- Stops API only if it started it

## Windows

Open PowerShell in the project folder and run:

```powershell
python .\run_uat_local.py --scale deep
```

## macOS / Linux

From terminal:

```bash
python3 run_uat_local.py --scale deep
```

## Outputs

- UAT report JSON: `uat_reports/uat_enterprise_report_<timestamp>.json`
- API log (if launcher started API): `uat_reports/local_api.log`
