#!/usr/bin/env python3
"""
Standalone Enterprise UAT Agent for ACAP.

Purpose:
- Seed complex, realistic synthetic enterprise audit data.
- Exercise end-to-end API flows used by the portal.
- Produce a structured UAT report with improvement candidates.

This script is intentionally separate from website code and can be run on demand.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import random
import statistics
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests


DEFAULT_BASE_URL = os.getenv("ACAP_BASE_URL", "http://127.0.0.1:8000")
DEFAULT_USERNAME = os.getenv("ACAP_UAT_USER", "admin")
DEFAULT_PASSWORD = os.getenv("ACAP_UAT_PASSWORD", "Audit123!")
API_PREFIX = "/api/v1"
REQUEST_TIMEOUT = 25


@dataclass
class ScaleProfile:
    evidence_events: int
    control_evaluations: int
    sod_conflicts: int
    governance_policies: int
    governance_mappings: int
    governance_risks: int
    alert_rules: int
    alerts: int
    ai_audit_cases: int


SCALE_PRESETS: Dict[str, ScaleProfile] = {
    "small": ScaleProfile(20, 12, 6, 3, 8, 6, 3, 6, 6),
    "medium": ScaleProfile(45, 24, 12, 5, 16, 12, 5, 12, 12),
    "deep": ScaleProfile(90, 48, 24, 8, 28, 20, 8, 24, 24),
}


class UATAgent:
    def __init__(self, base_url: str, username: str, password: str, scale: str, seed: int):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.scale_name = scale
        self.scale = SCALE_PRESETS[scale]
        self.seed = seed
        self.rand = random.Random(seed)

        self.session = requests.Session()

        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.report: Dict[str, Any] = {
            "run_id": self.run_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "config": {
                "base_url": self.base_url,
                "username": self.username,
                "scale": self.scale_name,
                "seed": self.seed,
            },
            "steps": [],
            "summary": {},
            "improvement_candidates": [],
            "artifacts": {},
        }

        self.latencies_ms: List[float] = []
        self.created: Dict[str, List[str]] = {
            "evidence_ids": [],
            "control_ids": [],
            "exception_ids": [],
            "framework_ids": [],
            "policy_ids": [],
            "mapping_ids": [],
            "risk_ids": [],
            "alert_rule_ids": [],
            "alert_ids": [],
            "report_run_ids": [],
            "ai_audit_case_ids": [],
        }

    def _csv_bytes(self, headers: List[str], rows: List[Dict[str, Any]]) -> bytes:
        buf = io.StringIO(newline="")
        writer = csv.DictWriter(buf, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
        return buf.getvalue().encode("utf-8")

    def _record_step(
        self,
        name: str,
        method: str,
        path: str,
        status_code: int,
        latency_ms: float,
        success: bool,
        details: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        entry: Dict[str, Any] = {
            "name": name,
            "method": method,
            "path": path,
            "status_code": status_code,
            "latency_ms": round(latency_ms, 2),
            "success": success,
        }
        if details:
            entry["details"] = details
        if error:
            entry["error"] = error
        self.report["steps"].append(entry)

    def _request(
        self,
        name: str,
        method: str,
        path: str,
        expected_status: Optional[List[int]] = None,
        required: bool = False,
        **kwargs: Any,
    ) -> Tuple[Optional[requests.Response], Any]:
        url = f"{self.base_url}{API_PREFIX}{path}"
        started = time.perf_counter()
        status_code = 0
        body: Any = None
        max_retries = 2
        attempts = max_retries + 1
        retryable_server_codes = {500, 502, 503, 504}

        for attempt in range(1, attempts + 1):
            try:
                response = self.session.request(method, url, timeout=REQUEST_TIMEOUT, **kwargs)
                status_code = response.status_code

                try:
                    body = response.json()
                except Exception:
                    body = response.text

                success = expected_status is None or status_code in expected_status
                retryable_status = status_code in retryable_server_codes and attempt < attempts

                if not success and retryable_status:
                    time.sleep(0.2 * attempt)
                    continue

                latency_ms = (time.perf_counter() - started) * 1000.0
                self.latencies_ms.append(latency_ms)
                details = {"url": url, "attempts": attempt}
                self._record_step(
                    name=name,
                    method=method,
                    path=path,
                    status_code=status_code,
                    latency_ms=latency_ms,
                    success=success,
                    details=details,
                    error=None if success else f"Unexpected status: {status_code}",
                )

                if required and not success:
                    raise RuntimeError(f"{name} failed with status {status_code}: {body}")
                return response, body

            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
                if attempt < attempts:
                    time.sleep(0.2 * attempt)
                    continue

                latency_ms = (time.perf_counter() - started) * 1000.0
                self.latencies_ms.append(latency_ms)
                self._record_step(
                    name=name,
                    method=method,
                    path=path,
                    status_code=status_code,
                    latency_ms=latency_ms,
                    success=False,
                    error=str(exc),
                )
                if required:
                    raise
                return None, None

            except Exception as exc:
                latency_ms = (time.perf_counter() - started) * 1000.0
                self.latencies_ms.append(latency_ms)
                self._record_step(
                    name=name,
                    method=method,
                    path=path,
                    status_code=status_code,
                    latency_ms=latency_ms,
                    success=False,
                    error=str(exc),
                )
                if required:
                    raise
                return None, None

        return None, None

    def authenticate(self) -> None:
        payload = {"username": self.username, "password": self.password}
        _, body = self._request(
            name="auth_login",
            method="POST",
            path="/auth/login",
            expected_status=[200],
            required=True,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        token = body.get("access_token")
        if not token:
            raise RuntimeError("Login succeeded but no access token returned.")
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def seed_evidence(self) -> None:
        sources = [
            "SAP-S4HANA",
            "Oracle-Fusion",
            "Workday-HCM",
            "ServiceNow-GRC",
            "Azure-AD",
            "Okta-SSO",
            "CyberArk-PAM",
            "Snowflake-DW",
        ]
        event_types = [
            "access_attempt",
            "role_change",
            "policy_violation",
            "config_change",
            "privileged_session",
            "vendor_master_update",
            "invoice_override",
            "payment_release",
        ]
        business_units = ["Finance", "Treasury", "Procurement", "HR", "Manufacturing", "SharedServices"]
        countries = ["US", "DE", "IN", "GB", "AE", "SG", "BR", "ZA"]

        for idx in range(self.scale.evidence_events):
            src = self.rand.choice(sources)
            evt = self.rand.choice(event_types)
            confidence = self.rand.randint(58, 99)
            amount = round(self.rand.uniform(2500, 420000), 2)
            payload = {
                "source_system": src,
                "event_type": evt,
                "log_data": (
                    f"{evt} detected in {src}; run={self.run_id}; event_idx={idx}; "
                    f"amount={amount}; user=USR-{self.rand.randint(1000, 9999)}"
                ),
                "metadata_json": {
                    "confidence": confidence,
                    "currency": "USD",
                    "amount": amount,
                    "legal_entity": f"LE-{self.rand.randint(10, 99)}",
                    "business_unit": self.rand.choice(business_units),
                    "country": self.rand.choice(countries),
                    "quarter": self.rand.choice(["Q1", "Q2", "Q3", "Q4"]),
                    "simulated": True,
                    "scenario_class": "enterprise_uat",
                },
            }
            _, body = self._request(
                name=f"seed_evidence_{idx}",
                method="POST",
                path="/audit/evidence",
                expected_status=[201],
                json=payload,
            )
            rec_id = body.get("id") if isinstance(body, dict) else None
            if rec_id:
                self.created["evidence_ids"].append(str(rec_id))

    def seed_control_evaluations(self) -> None:
        families = [
            "ITGC-ACCESS",
            "ITGC-CHANGE",
            "ITGC-OPS",
            "ITAC-P2P",
            "ITAC-R2R",
            "ITAC-I2P",
            "FRAUD-DETECT",
        ]
        statuses = ["passed", "failed", "exception"]
        weights = [0.56, 0.27, 0.17]

        for idx in range(self.scale.control_evaluations):
            family = self.rand.choice(families)
            status = self.rand.choices(statuses, weights=weights, k=1)[0]
            records_tested = self.rand.randint(250, 9500)
            fail_count = self.rand.randint(0, max(1, int(records_tested * 0.18)))
            payload = {
                "control_id": f"{family}-{self.run_id[-6:]}-{idx:03d}",
                "description": (
                    f"Synthetic enterprise test for {family} across multi-entity flows, "
                    f"approval hierarchy, and policy thresholds"
                ),
                "test_type": self.rand.choice(["Automated", "Hybrid", "Continuous", "Detective"]),
                "status": status,
                "metrics": {
                    "records_tested": records_tested,
                    "records_failed": fail_count,
                    "threshold_pct": round(self.rand.uniform(0.2, 4.0), 2),
                    "observed_pct": round((fail_count / max(records_tested, 1)) * 100, 2),
                    "entity_count": self.rand.randint(2, 11),
                    "country_count": self.rand.randint(2, 8),
                    "source_mix": ["ERP", "IAM", "PAM", "ITSM"],
                    "run_id": self.run_id,
                },
            }
            _, body = self._request(
                name=f"seed_control_eval_{idx}",
                method="POST",
                path="/evaluation/controls",
                expected_status=[201],
                json=payload,
            )
            rec_id = body.get("id") if isinstance(body, dict) else None
            if rec_id:
                self.created["control_ids"].append(str(rec_id))

    def seed_sod_conflicts(self) -> None:
        role_pairs = [
            ("vendor_create", "vendor_pay"),
            ("journal_create", "journal_post"),
            ("payment_proposal", "payment_release"),
            ("user_admin", "role_approver"),
            ("po_create", "po_approve"),
            ("gl_master_change", "posting_execute"),
        ]
        severities = ["High", "Critical", "Medium", "High", "Critical"]

        for idx in range(self.scale.sod_conflicts):
            role_a, role_b = self.rand.choice(role_pairs)
            payload = {
                "user_id": f"UAT-USER-{self.rand.randint(10000, 99999)}",
                "role_a": role_a,
                "role_b": role_b,
                "conflict_type": "toxic_combination",
                "risk_level": self.rand.choice(severities),
            }
            self._request(
                name=f"seed_sod_{idx}",
                method="POST",
                path="/evaluation/sod",
                expected_status=[201],
                json=payload,
            )

    def seed_exceptions_and_lifecycle(self) -> None:
        _, controls = self._request(
            name="list_controls_for_exceptions",
            method="GET",
            path="/evaluation/controls",
            expected_status=[200],
        )
        controls = controls if isinstance(controls, list) else []
        failed_controls = [c for c in controls if c.get("status") in {"failed", "exception"}]
        target = min(8, len(failed_controls))
        for idx in range(target):
            c = failed_controls[idx]
            payload = {
                "control_test_id": c["id"],
                "description": (
                    "Exception opened by enterprise UAT for remediation workflow testing "
                    f"on control {c.get('control_id')}"
                ),
                "owner_id": f"owner_{idx % 4}@examplecorp.test",
            }
            _, body = self._request(
                name=f"create_exception_{idx}",
                method="POST",
                path="/evaluation/exceptions",
                expected_status=[201],
                json=payload,
            )
            ex_id = body.get("id") if isinstance(body, dict) else None
            if not ex_id:
                continue
            self.created["exception_ids"].append(str(ex_id))

            lifecycle = ["acknowledged", "remediation_in_progress", "remediated", "closed"]
            if idx % 3 == 1:
                lifecycle = ["accepted_risk", "closed"]

            for step in lifecycle:
                self._request(
                    name=f"transition_exception_{idx}_{step}",
                    method="PATCH",
                    path=f"/evaluation/exceptions/{ex_id}/transition",
                    expected_status=[200],
                    json={"new_state": step, "comment": f"UAT transition to {step}"},
                )

    def seed_governance(self) -> None:
        framework_catalog = [
            ("SOX404", "SOX Internal Control", "2025"),
            ("ISO27001", "ISO 27001", "2022"),
            ("COBIT2019", "COBIT", "2019"),
            ("NIST-CSF", "NIST Cybersecurity Framework", "2.0"),
        ]

        selected_frameworks = framework_catalog[: min(len(framework_catalog), 3)]
        for fw_id, name, version in selected_frameworks:
            payload = {
                "framework_id": f"{fw_id}-{self.run_id[-4:]}",
                "name": name,
                "version": version,
                "description": f"Synthetic framework for UAT run {self.run_id}",
                "is_active": True,
            }
            _, body = self._request(
                name=f"create_framework_{fw_id}",
                method="POST",
                path="/governance/frameworks",
                expected_status=[201],
                json=payload,
            )
            if isinstance(body, dict) and body.get("framework_id"):
                self.created["framework_ids"].append(body["framework_id"])

        for idx in range(self.scale.governance_policies):
            payload = {
                "policy_id": f"POL-UAT-{self.run_id[-6:]}-{idx:03d}",
                "title": f"Enterprise UAT Policy {idx:03d}",
                "description": "Complex multi-entity policy for approval, segregation, and monitoring controls.",
                "owner": f"governance.owner{idx % 5}@examplecorp.test",
                "status": self.rand.choice(["active", "active", "draft", "under_review"]),
                "version": f"1.{idx % 9}",
                "framework_refs": self.created["framework_ids"][:2],
            }
            _, body = self._request(
                name=f"create_policy_{idx}",
                method="POST",
                path="/governance/policies",
                expected_status=[201],
                json=payload,
            )
            if isinstance(body, dict) and body.get("policy_id"):
                self.created["policy_ids"].append(body["policy_id"])

        frameworks = self.created["framework_ids"] or [f"SOX404-{self.run_id[-4:]}"]
        for idx in range(self.scale.governance_mappings):
            fw = frameworks[idx % len(frameworks)]
            payload = {
                "framework_id": fw,
                "requirement_ref": f"REQ-{idx % 20:03d}",
                "control_id": f"CTRL-UAT-{idx:03d}",
                "mapping_status": self.rand.choice(["mapped", "mapped", "partial", "gap"]),
                "notes": "Synthetic requirement-to-control mapping for UAT scenario coverage.",
            }
            _, body = self._request(
                name=f"create_mapping_{idx}",
                method="POST",
                path="/governance/mappings",
                expected_status=[201],
                json=payload,
            )
            if isinstance(body, dict) and body.get("id"):
                self.created["mapping_ids"].append(str(body["id"]))

        categories = ["Financial", "Cyber", "Operational", "ThirdParty", "Regulatory", "DataQuality"]
        treatments = ["mitigate", "transfer", "accept", "avoid"]
        for idx in range(self.scale.governance_risks):
            il = self.rand.randint(2, 5)
            ii = self.rand.randint(2, 5)
            rl = max(1, il - self.rand.randint(0, 2))
            ri = max(1, ii - self.rand.randint(0, 2))
            payload = {
                "risk_id": f"RISK-UAT-{self.run_id[-6:]}-{idx:03d}",
                "title": f"Enterprise risk scenario {idx:03d}",
                "description": "Synthetic industry-like risk scenario covering controls, legal entities, and cross-border operations.",
                "category": self.rand.choice(categories),
                "inherent_likelihood": il,
                "inherent_impact": ii,
                "residual_likelihood": rl,
                "residual_impact": ri,
                "owner": f"risk.owner{idx % 6}@examplecorp.test",
                "treatment": self.rand.choice(treatments),
                "status": self.rand.choice(["open", "open", "monitoring", "mitigated"]),
                "related_controls": [f"CTRL-UAT-{idx:03d}", f"CTRL-UAT-{(idx + 1) % 40:03d}"],
            }
            _, body = self._request(
                name=f"create_risk_{idx}",
                method="POST",
                path="/governance/risks",
                expected_status=[201],
                json=payload,
            )
            if isinstance(body, dict) and body.get("risk_id"):
                self.created["risk_ids"].append(body["risk_id"])

    def seed_alerts(self) -> None:
        metrics = [
            "failed_controls_count",
            "critical_findings_count",
            "sod_conflicts_count",
            "open_exceptions_count",
            "high_risk_count",
            "tampered_records_count",
        ]
        severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

        for idx in range(self.scale.alert_rules):
            payload = {
                "rule_id": f"ALERT-RULE-UAT-{self.run_id[-5:]}-{idx:03d}",
                "name": f"UAT Rule {idx:03d}",
                "description": "Synthetic threshold rule for continuous assurance validation.",
                "metric": metrics[idx % len(metrics)],
                "operator": self.rand.choice(["gte", "gt", "eq"]),
                "threshold": self.rand.randint(1, 35),
                "severity": self.rand.choice(severities),
                "is_active": True,
            }
            _, body = self._request(
                name=f"create_alert_rule_{idx}",
                method="POST",
                path="/alerts/rules",
                expected_status=[201],
                json=payload,
            )
            if isinstance(body, dict) and body.get("id"):
                self.created["alert_rule_ids"].append(str(body["id"]))

        rules = self.created["alert_rule_ids"]
        for idx in range(self.scale.alerts):
            payload = {
                "title": f"UAT Compliance Alert {idx:03d}",
                "description": (
                    "Synthetic scenario: cascading control breakdown across geographies, "
                    "late remediation, and unresolved segregation conflicts"
                ),
                "severity": self.rand.choice(severities),
                "alert_rule_id": rules[idx % len(rules)] if rules else None,
                "metric_value": self.rand.randint(1, 120),
                "affected_controls": [f"CTRL-UAT-{idx:03d}", f"CTRL-UAT-{(idx + 5) % 50:03d}"],
            }
            _, body = self._request(
                name=f"create_alert_{idx}",
                method="POST",
                path="/alerts/",
                expected_status=[201],
                json=payload,
            )
            alert_id = body.get("id") if isinstance(body, dict) else None
            if not alert_id:
                continue
            self.created["alert_ids"].append(str(alert_id))

            if idx % 2 == 0:
                self._request(
                    name=f"ack_alert_{idx}",
                    method="PATCH",
                    path=f"/alerts/{alert_id}/acknowledge",
                    expected_status=[200],
                    json={"comment": "UAT acknowledge"},
                )
            if idx % 3 == 0:
                self._request(
                    name=f"resolve_alert_{idx}",
                    method="PATCH",
                    path=f"/alerts/{alert_id}/resolve",
                    expected_status=[200],
                    json={"comment": "UAT resolve"},
                )

    def exercise_engine_and_reports(self) -> None:
        self._request(
            name="engine_health",
            method="GET",
            path="/engine/health",
            expected_status=[200],
        )

        users_payload: Dict[str, List[str]] = {}
        role_sets = [
            ["create_vendor", "pay_vendor", "journal_post"],
            ["po_create", "po_approve"],
            ["role_admin", "user_admin", "role_approver"],
            ["journal_create", "journal_post"],
            ["invoice_post", "payment_release"],
        ]
        for idx in range(max(20, self.scale.sod_conflicts)):
            users_payload[f"uat.user.{idx:03d}"] = self.rand.choice(role_sets)

        self._request(
            name="engine_analyze_sod",
            method="POST",
            path="/engine/analyze/sod",
            expected_status=[200],
            json={"source_system": "Enterprise-UAT-Simulation", "users": users_payload},
        )

        report_types = [
            "executive_summary",
            "compliance_status",
            "kpi_dashboard",
            "audit_findings",
            "sod_matrix",
            "risk_register",
            "continuous_assurance",
        ]
        for rtype in report_types:
            _, body = self._request(
                name=f"run_report_{rtype}",
                method="POST",
                path="/reports/runs",
                expected_status=[201],
                json={
                    "report_type": rtype,
                    "name": f"UAT {rtype} {self.run_id}",
                    "parameters": {
                        "run_id": self.run_id,
                        "scope": "enterprise",
                        "generated_by": "uat_enterprise_agent",
                    },
                },
            )
            if isinstance(body, dict) and body.get("id"):
                self.created["report_run_ids"].append(str(body["id"]))

    def run_ai_audit_scenarios(self) -> None:
        """
        Runs complex Audit-of-AI stress scenarios through engine endpoints.

        Scenarios intentionally mix clean and flawed records to validate:
        - toxic access combinations and dormant privileged users
        - change self-approval and missing test evidence
        - ITAC 3-way match bypass and high-value approval issues
        - interface reconciliation mismatches
        """
        scenario_kinds = [
            "users_toxic_sod",
            "users_dormant_privileged",
            "changes_self_approval",
            "transactions_three_way_bypass",
            "interfaces_recon_mismatch",
        ]

        for idx in range(self.scale.ai_audit_cases):
            kind = scenario_kinds[idx % len(scenario_kinds)]
            case_id = f"AIAUD-{self.run_id[-6:]}-{idx:03d}"
            self.created["ai_audit_case_ids"].append(case_id)

            headers: List[str]
            rows: List[Dict[str, Any]]
            filename = f"{kind}_{case_id}.csv"

            if kind == "users_toxic_sod":
                headers = [
                    "user_id",
                    "status",
                    "roles",
                    "last_login_date",
                    "mfa_enabled",
                    "access_review_date",
                ]
                rows = [
                    {
                        "user_id": f"usr_{case_id}_001",
                        "status": "active",
                        "roles": "create_vendor,pay_vendor",
                        "last_login_date": "2026-02-25",
                        "mfa_enabled": "No",
                        "access_review_date": "2024-06-01",
                    },
                    {
                        "user_id": f"usr_{case_id}_002",
                        "status": "active",
                        "roles": "journal_create,journal_post",
                        "last_login_date": "2026-03-01",
                        "mfa_enabled": "Yes",
                        "access_review_date": "2025-12-01",
                    },
                ]
            elif kind == "users_dormant_privileged":
                headers = [
                    "user_id",
                    "status",
                    "roles",
                    "last_login_date",
                    "termination_date",
                    "mfa_enabled",
                    "access_review_date",
                ]
                rows = [
                    {
                        "user_id": f"usr_{case_id}_003",
                        "status": "active",
                        "roles": "role_admin,user_admin",
                        "last_login_date": "2025-01-03",
                        "termination_date": "",
                        "mfa_enabled": "No",
                        "access_review_date": "2023-11-11",
                    },
                    {
                        "user_id": f"usr_{case_id}_004",
                        "status": "terminated",
                        "roles": "payment_release",
                        "last_login_date": "2026-02-20",
                        "termination_date": "2025-12-31",
                        "mfa_enabled": "Yes",
                        "access_review_date": "2025-03-15",
                    },
                ]
            elif kind == "changes_self_approval":
                headers = [
                    "ticket_id",
                    "change_type",
                    "initiator",
                    "approver",
                    "environment",
                    "implementation_date",
                    "test_evidence",
                    "post_impl_review",
                    "status",
                ]
                rows = [
                    {
                        "ticket_id": f"CHG-{case_id}-01",
                        "change_type": "normal",
                        "initiator": "dev.lead",
                        "approver": "dev.lead",
                        "environment": "production",
                        "implementation_date": "2026-02-27",
                        "test_evidence": "No",
                        "post_impl_review": "No",
                        "status": "closed",
                    },
                    {
                        "ticket_id": f"CHG-{case_id}-02",
                        "change_type": "emergency",
                        "initiator": "ops.user",
                        "approver": "ops.manager",
                        "environment": "production",
                        "implementation_date": "2026-03-02",
                        "test_evidence": "Yes",
                        "post_impl_review": "No",
                        "status": "closed",
                    },
                ]
            elif kind == "transactions_three_way_bypass":
                headers = [
                    "invoice_id",
                    "vendor",
                    "invoice_amount",
                    "po_amount",
                    "gr_amount",
                    "three_way_match",
                    "approved_by",
                    "approver_level",
                    "invoice_date",
                ]
                rows = [
                    {
                        "invoice_id": f"INV-{case_id}-01",
                        "vendor": "Shadow Vendor Ltd",
                        "invoice_amount": "250000",
                        "po_amount": "100000",
                        "gr_amount": "98000",
                        "three_way_match": "bypass",
                        "approved_by": "clerk.ap",
                        "approver_level": "staff",
                        "invoice_date": "2026-03-03",
                    },
                    {
                        "invoice_id": f"INV-{case_id}-02",
                        "vendor": "Standard Vendor Inc",
                        "invoice_amount": "12000",
                        "po_amount": "12000",
                        "gr_amount": "12000",
                        "three_way_match": "pass",
                        "approved_by": "mgr.ap",
                        "approver_level": "manager",
                        "invoice_date": "2026-03-04",
                    },
                ]
            else:  # interfaces_recon_mismatch
                headers = [
                    "interface_id",
                    "interface_name",
                    "source_count",
                    "target_count",
                    "source_total",
                    "target_total",
                    "status",
                ]
                rows = [
                    {
                        "interface_id": f"INT-{case_id}-01",
                        "interface_name": "ERP_to_DWH",
                        "source_count": "10500",
                        "target_count": "10112",
                        "source_total": "7623000.00",
                        "target_total": "7401000.00",
                        "status": "completed",
                    },
                    {
                        "interface_id": f"INT-{case_id}-02",
                        "interface_name": "Payroll_to_GL",
                        "source_count": "1220",
                        "target_count": "1220",
                        "source_total": "4150000.00",
                        "target_total": "4150000.00",
                        "status": "completed",
                    },
                ]

            csv_payload = self._csv_bytes(headers, rows)
            _, body = self._request(
                name=f"ai_audit_analyze_{idx}_{kind}",
                method="POST",
                path="/engine/analyze",
                expected_status=[200],
                files={"file": (filename, csv_payload, "text/csv")},
                data={
                    "source_system": f"AI-AUDIT-UAT-{kind}",
                    "audit_period": f"Q{(idx % 4) + 1} 2026",
                },
            )

            findings = body.get("all_findings", []) if isinstance(body, dict) else []
            if findings:
                finding_id = findings[0].get("finding_id")
                if finding_id:
                    verdict = "confirmed" if idx % 2 == 0 else "false_positive"
                    self._request(
                        name=f"ai_audit_verdict_{idx}",
                        method="PATCH",
                        path=f"/engine/findings/{finding_id}/verdict",
                        expected_status=[200],
                        json={
                            "verdict": verdict,
                            "notes": f"UAT AI-audit case {case_id} classified as {verdict}",
                        },
                    )

        # Validation gate check with intentionally invalid schema.
        invalid_csv = self._csv_bytes(["foo", "bar"], [{"foo": "x", "bar": "y"}])
        self._request(
            name="ai_audit_validate_invalid_schema",
            method="POST",
            path="/engine/analyze/validate",
            expected_status=[200],
            files={"file": ("invalid_schema.csv", invalid_csv, "text/csv")},
        )

        # Accuracy endpoint should respond even when evidence is sparse.
        self._request(
            name="ai_audit_accuracy",
            method="GET",
            path="/engine/accuracy",
            expected_status=[200],
        )

    def collect_snapshots(self) -> Dict[str, Any]:
        snapshots: Dict[str, Any] = {}
        for name, path in [
            ("vault_summary", "/audit/vault/summary"),
            ("controls", "/evaluation/controls"),
            ("sod", "/evaluation/sod"),
            ("exceptions", "/evaluation/exceptions"),
            ("risks", "/governance/risks"),
            ("alerts", "/alerts/"),
            ("dashboard", "/reports/dashboard"),
            ("kpis", "/reports/kpis"),
            ("report_runs", "/reports/runs"),
            ("engine_accuracy", "/engine/accuracy"),
        ]:
            _, body = self._request(
                name=f"snapshot_{name}",
                method="GET",
                path=path,
                expected_status=[200],
                required=False,
            )
            snapshots[name] = body
        return snapshots

    def evaluate(self, snapshots: Dict[str, Any]) -> None:
        candidates = self.report["improvement_candidates"]

        failed_steps = [s for s in self.report["steps"] if not s.get("success")]
        if failed_steps:
            candidates.append(
                {
                    "type": "api_failures",
                    "severity": "high",
                    "summary": f"{len(failed_steps)} API steps failed during UAT run",
                    "evidence": failed_steps[:20],
                }
            )

        if self.latencies_ms:
            p95 = statistics.quantiles(self.latencies_ms, n=20)[18] if len(self.latencies_ms) >= 20 else max(self.latencies_ms)
            if p95 > 900:
                candidates.append(
                    {
                        "type": "latency",
                        "severity": "medium",
                        "summary": f"P95 API latency is high ({round(p95, 2)} ms)",
                        "evidence": {"p95_ms": round(p95, 2), "max_ms": round(max(self.latencies_ms), 2)},
                    }
                )

        kpis_raw = snapshots.get("kpis")
        alerts_raw = snapshots.get("alerts")
        kpis = kpis_raw if isinstance(kpis_raw, dict) else {}
        alerts = alerts_raw if isinstance(alerts_raw, list) else []
        open_alerts_live = len([a for a in alerts if a.get("status") == "open"])
        kpi_open_alerts = kpis.get("open_alerts")
        if isinstance(kpi_open_alerts, int) and abs(kpi_open_alerts - open_alerts_live) > 2:
            candidates.append(
                {
                    "type": "consistency",
                    "severity": "medium",
                    "summary": "Mismatch between KPI open_alerts and live alert list",
                    "evidence": {
                        "kpi_open_alerts": kpi_open_alerts,
                        "open_alerts_live": open_alerts_live,
                    },
                }
            )

        controls_created = len(self.created["control_ids"])
        controls_raw = snapshots.get("controls")
        controls_list = controls_raw if isinstance(controls_raw, list) else []
        if controls_created > 0 and len(controls_list) < min(controls_created, 20):
            candidates.append(
                {
                    "type": "coverage",
                    "severity": "low",
                    "summary": "Evaluation controls list may be truncated for heavy UAT scenarios",
                    "evidence": {
                        "controls_created": controls_created,
                        "controls_list_count": len(controls_list),
                        "note": "Consider pagination/filtering strategy checks in UI",
                    },
                }
            )

        ai_steps = [s for s in self.report["steps"] if s.get("name", "").startswith("ai_audit_analyze_")]
        ai_success = [s for s in ai_steps if s.get("success")]
        if ai_steps and len(ai_success) < max(1, int(len(ai_steps) * 0.7)):
            candidates.append(
                {
                    "type": "ai_audit_coverage",
                    "severity": "high",
                    "summary": "AI-audit complex scenarios show low pass rate in engine endpoints",
                    "evidence": {
                        "total_ai_audit_cases": len(ai_steps),
                        "successful_cases": len(ai_success),
                    },
                }
            )

        accuracy_raw = snapshots.get("engine_accuracy")
        if isinstance(accuracy_raw, dict):
            precision_val = accuracy_raw.get("precision")
            if isinstance(precision_val, (int, float)) and precision_val < 85:
                candidates.append(
                    {
                        "type": "ai_model_precision",
                        "severity": "medium",
                        "summary": f"Engine precision is below target ({precision_val}%) for reviewed findings",
                        "evidence": accuracy_raw,
                    }
                )

    def finalize(self, snapshots: Dict[str, Any]) -> Path:
        self.report["finished_at"] = datetime.now(timezone.utc).isoformat()
        self.report["artifacts"]["snapshots"] = snapshots
        self.report["artifacts"]["created_objects"] = self.created

        total_steps = len(self.report["steps"])
        failed_steps = len([s for s in self.report["steps"] if not s.get("success")])
        self.report["summary"] = {
            "total_steps": total_steps,
            "failed_steps": failed_steps,
            "success_rate_pct": round(((total_steps - failed_steps) / max(total_steps, 1)) * 100, 2),
            "p95_latency_ms": (
                round(statistics.quantiles(self.latencies_ms, n=20)[18], 2)
                if len(self.latencies_ms) >= 20
                else round(max(self.latencies_ms), 2) if self.latencies_ms else None
            ),
            "created_counts": {k: len(v) for k, v in self.created.items()},
            "improvement_candidates": len(self.report["improvement_candidates"]),
        }

        reports_dir = Path("uat_reports")
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / f"uat_enterprise_report_{self.run_id}.json"
        report_path.write_text(json.dumps(self.report, indent=2), encoding="utf-8")
        return report_path

    def run(self) -> Path:
        self.authenticate()
        self.seed_evidence()
        self.seed_control_evaluations()
        self.seed_sod_conflicts()
        self.seed_exceptions_and_lifecycle()
        self.seed_governance()
        self.seed_alerts()
        self.exercise_engine_and_reports()
        self.run_ai_audit_scenarios()
        snapshots = self.collect_snapshots()
        self.evaluate(snapshots)
        return self.finalize(snapshots)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Standalone enterprise UAT agent for ACAP API and portal logic coverage."
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="ACAP base URL, e.g. http://127.0.0.1:8000")
    parser.add_argument("--username", default=DEFAULT_USERNAME, help="API username for /auth/login")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="API password for /auth/login")
    parser.add_argument("--scale", choices=sorted(SCALE_PRESETS.keys()), default="deep", help="Data volume profile")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible synthetic scenarios")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(f"[UAT] Starting enterprise UAT agent against {args.base_url} (scale={args.scale}, seed={args.seed})")
    agent = UATAgent(
        base_url=args.base_url,
        username=args.username,
        password=args.password,
        scale=args.scale,
        seed=args.seed,
    )

    try:
        report_path = agent.run()
        summary = agent.report.get("summary", {})
        print("[UAT] Completed")
        print(f"[UAT] Report: {report_path}")
        print(f"[UAT] Steps: {summary.get('total_steps')} | Failed: {summary.get('failed_steps')} | P95(ms): {summary.get('p95_latency_ms')}")
        print(f"[UAT] Improvement candidates: {summary.get('improvement_candidates')}")
        return 0
    except Exception as exc:
        print(f"[UAT] Failed: {exc}")
        try:
            snapshots = agent.collect_snapshots()
            report_path = agent.finalize(snapshots)
            print(f"[UAT] Partial report saved: {report_path}")
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
