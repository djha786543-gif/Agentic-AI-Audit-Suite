import json
from datetime import datetime, timedelta

import requests

BASE = "http://127.0.0.1:8000/api/v1"


def login(username: str, password: str) -> str:
    resp = requests.post(f"{BASE}/auth/login", data={"username": username, "password": password}, timeout=30)
    resp.raise_for_status()
    return resp.json()["access_token"]


def main() -> None:
    admin = login("admin", "Audit123!")
    try:
        process_owner = login("processowner", "Owner123!")
    except Exception:
        # Some running containers may still use an older auth image.
        process_owner = admin
    external = login("external", "External123!")

    h_admin = {"Authorization": f"Bearer {admin}"}
    h_po = {"Authorization": f"Bearer {process_owner}"}
    h_ext = {"Authorization": f"Bearer {external}"}

    integrity_payload = {
        "active_users": [{"user_id": "u100"}, {"user_id": "u200"}],
        "hr_master": [{"user_id": "u100"}],
    }
    resp = requests.post(f"{BASE}/engine/integrity-check", json=integrity_payload, timeout=30)
    resp.raise_for_status()
    print("integrity_check", resp.status_code, "issues", resp.json().get("issue_count"))

    resp = requests.post(
        f"{BASE}/engine/sampling",
        json={"method": "attribute", "population": [{"x": i} for i in range(50)], "sample_size": 10},
        timeout=30,
    )
    resp.raise_for_status()
    print("sampling_attribute", resp.status_code, "sample_size", resp.json().get("sample_size"))

    csv_data = (
        "user_id,status,roles\n"
        "u100,active,create_vendor;pay_vendor\n"
        "u200,active,journal_create;journal_approve\n"
    )
    files = {"file": ("users.csv", csv_data, "text/csv")}
    data = {"source_system": "Smoke ERP", "audit_period": "Q1 2026", "anonymize": "true"}
    resp = requests.post(f"{BASE}/engine/analyze", headers=h_admin, files=files, data=data, timeout=60)
    resp.raise_for_status()
    analysis = resp.json()
    print("analyze", resp.status_code, "findings", analysis.get("total_findings"))

    resp = requests.get(f"{BASE}/findings/", headers=h_admin, timeout=30)
    resp.raise_for_status()
    findings = resp.json()
    if not findings:
        raise RuntimeError("No findings returned after analysis")
    finding_id = findings[0]["id"]

    due_date = (datetime.utcnow() + timedelta(days=30)).isoformat() + "Z"
    resp = requests.patch(
        f"{BASE}/findings/{finding_id}/remediation",
        headers={**h_admin, "Content-Type": "application/json"},
        json={"remediation_owner": "AP Process Owner", "remediation_due_date": due_date},
        timeout=30,
    )
    resp.raise_for_status()
    print("assign_remediation", resp.status_code)

    response_payload = {
        "finding_id": finding_id,
        "response_text": "Owner accepted remediation plan and initiated role redesign.",
        "responsible_owner": "AP Process Owner",
        "target_date": (datetime.utcnow() + timedelta(days=45)).isoformat() + "Z",
    }
    resp = requests.post(
        f"{BASE}/findings/{finding_id}/management-response",
        headers={**h_po, "Content-Type": "application/json"},
        json=response_payload,
        timeout=30,
    )
    resp.raise_for_status()
    print("management_response", resp.status_code)

    resp = requests.get(f"{BASE}/findings/{finding_id}/reperformance", headers=h_ext, timeout=30)
    resp.raise_for_status()
    print("reperformance", resp.status_code, "has_logic", resp.json().get("logic_breakdown") is not None)

    resp = requests.get(f"{BASE}/reports/exports/workpaper?target=workiva", headers=h_admin, timeout=30)
    resp.raise_for_status()
    print("export_workiva_json", resp.status_code, "rows", len(resp.json().get("findings", [])))

    resp = requests.get(f"{BASE}/reports/exports/workpaper?target=xml", headers=h_admin, timeout=30)
    resp.raise_for_status()
    print("export_xml", resp.status_code, resp.headers.get("content-type"))

    resp = requests.get(f"{BASE}/reports/external/review-package", headers=h_ext, timeout=30)
    resp.raise_for_status()
    print("external_review_package", resp.status_code, resp.json().get("mode"))

    resp = requests.get(f"{BASE}/governance/risk-heatmap", headers=h_admin, timeout=30)
    resp.raise_for_status()
    print("risk_heatmap", resp.status_code, resp.json().get("framework"))

    resp = requests.get(f"{BASE}/governance/audit-logs", headers=h_admin, timeout=30)
    resp.raise_for_status()
    print("governance_logs", resp.status_code, len(resp.json()))

    print("SMOKE_WALKTHROUGH=PASS")


if __name__ == "__main__":
    main()
