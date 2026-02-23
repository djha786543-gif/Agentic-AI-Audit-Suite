"""
watcher_agent.py — streams evidence to the vault every 3 seconds.
Now authenticates with JWT before posting. Reads API_HOST/PORT from env.
"""
import requests
import time
import random
import os
from datetime import datetime, timezone

API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = os.getenv("API_PORT", "8000")
BASE_URL = f"http://{API_HOST}:{API_PORT}"

SYSTEMS = ["FileSystem-Watcher", "Windows-Security-Logs", "Azure-AD", "Network-Firewall"]
EVENTS  = ["access_attempt", "login_success", "policy_violation", "config_change"]


def get_token():
    try:
        username = os.getenv("API_USER", "admin")
        password = os.getenv("API_PASSWORD", "Audit123!")
        r = requests.post(f"{BASE_URL}/api/v1/auth/login",
                          data={"username": username, "password": password},
                          timeout=5)
        if r.status_code == 200:
            return r.json()["access_token"]
    except Exception as e:
        print(f"  Auth error: {e}")
    return None


def run():
    print(f"  ACAP Watcher → {BASE_URL}")
    print("  Authenticating...")
    token = None
    last_heartbeat = 0

    while True:
        if not token:
            token = get_token()
            if not token:
                print("  ⚠  Cannot auth — retrying in 5s...")
                time.sleep(5)
                continue
            print("  ✓  Token acquired\n")

        now = time.time()
        if now - last_heartbeat >= 30:
            try:
                requests.post(f"{BASE_URL}/api/v1/audit/runs/heartbeat", timeout=5)
                last_heartbeat = now
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ♥  Heartbeat sent to extraction_runs")
            except Exception as e:
                print(f"  ✗ Heartbeat error: {e}")

        src  = random.choice(SYSTEMS)
        evt  = random.choice(EVENTS)
        conf = random.randint(60, 100)

        payload = {
            "source_system": src,
            "event_type": evt,
            "log_data": f"Event from {src} at {datetime.now(timezone.utc).isoformat()}",
            "metadata_json": {"confidence": conf, "simulated": True},
        }

        try:
            r = requests.post(
                f"{BASE_URL}/api/v1/audit/evidence",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=5,
            )
            if r.status_code == 201:
                data = r.json()
                print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                      f"✓  {src:25s} | {evt:18s} | "
                      f"hash={(data.get('content_hash') or data.get('hash_sequence','?'))[:12]}…")
            elif r.status_code == 401:
                print("  Token expired — re-authenticating...")
                token = None
            else:
                print(f"  ✗  HTTP {r.status_code}: {r.text[:80]}")
        except requests.exceptions.ConnectionError:
            print(f"  ⚠  Cannot reach {BASE_URL} — waiting...")
        except Exception as e:
            print(f"  ✗  {e}")

        time.sleep(3)


if __name__ == "__main__":
    run()
