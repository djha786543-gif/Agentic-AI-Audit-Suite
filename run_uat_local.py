#!/usr/bin/env python3
"""
Desktop-friendly local UAT launcher.

What it does:
1. Ensures a local virtual environment exists (.venv)
2. Installs requirements.txt if needed
3. Starts API server if not already running
4. Runs the standalone UAT agent
5. Optionally runs the diff utility

Usage:
  python run_uat_local.py --scale deep
  python run_uat_local.py --scale small --port 8000 --seed 42
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
REQ_FILE = ROOT / "requirements.txt"
INSTALL_STAMP = VENV_DIR / ".deps_installed"


def venv_python() -> Path:
    if platform.system().lower().startswith("win"):
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def is_api_alive(base_url: str) -> bool:
    url = f"{base_url}/api/v1/health"
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> int:
    print("[RUN]", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=cwd, check=check)
    return proc.returncode


def ensure_venv() -> Path:
    py = venv_python()
    if py.exists():
        return py

    print("[SETUP] Creating virtual environment...")
    run([sys.executable, "-m", "venv", str(VENV_DIR)], cwd=ROOT)
    py = venv_python()
    if not py.exists():
        raise RuntimeError("Could not create virtual environment")
    return py


def ensure_deps(py: Path) -> None:
    if INSTALL_STAMP.exists() and INSTALL_STAMP.stat().st_mtime >= REQ_FILE.stat().st_mtime:
        print("[SETUP] Dependencies already installed")
        return

    print("[SETUP] Installing dependencies from requirements.txt...")
    run([str(py), "-m", "pip", "install", "--upgrade", "pip"], cwd=ROOT)
    run([str(py), "-m", "pip", "install", "-r", str(REQ_FILE)], cwd=ROOT)
    INSTALL_STAMP.write_text("ok\n", encoding="utf-8")


def start_api(py: Path, port: int) -> subprocess.Popen:
    print(f"[API] Starting local API on port {port}...")
    log_path = ROOT / "uat_reports" / "local_api.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(log_path, "a", encoding="utf-8")
    proc = subprocess.Popen(
        [str(py), "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT,
        stdout=log_file,
        stderr=log_file,
    )
    return proc


def wait_for_api(base_url: str, timeout_sec: int = 60) -> bool:
    start = time.time()
    while (time.time() - start) < timeout_sec:
        if is_api_alive(base_url):
            return True
        time.sleep(1)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Local desktop UAT launcher")
    parser.add_argument("--scale", choices=["small", "medium", "deep"], default="deep")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--run-diff", action="store_true", help="Run compare utility after UAT")
    args = parser.parse_args()

    base_url = f"http://127.0.0.1:{args.port}"

    py = ensure_venv()
    ensure_deps(py)

    api_proc = None
    started_here = False

    try:
        if is_api_alive(base_url):
            print(f"[API] Reusing existing API at {base_url}")
        else:
            api_proc = start_api(py, args.port)
            started_here = True
            if not wait_for_api(base_url):
                raise RuntimeError(
                    f"API did not become healthy at {base_url}/api/v1/health. "
                    f"Check uat_reports/local_api.log"
                )
            print(f"[API] Healthy at {base_url}")

        run(
            [
                str(py),
                str(ROOT / "agents" / "uat_enterprise_agent.py"),
                "--base-url", base_url,
                "--scale", args.scale,
                "--seed", str(args.seed),
            ],
            cwd=ROOT,
        )

        if args.run_diff:
            run([str(py), str(ROOT / "agents" / "compare_uat_reports.py")], cwd=ROOT, check=False)

        print("[DONE] UAT execution completed.")
        print("[DONE] Reports are in: uat_reports/")
        return 0

    except subprocess.CalledProcessError as exc:
        print(f"[ERROR] Command failed with exit code {exc.returncode}")
        return exc.returncode
    except Exception as exc:
        print(f"[ERROR] {exc}")
        return 1
    finally:
        if started_here and api_proc is not None:
            print("[API] Stopping API started by launcher...")
            api_proc.terminate()
            try:
                api_proc.wait(timeout=8)
            except Exception:
                api_proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
