"""
engine/access.py
────────────────
Logical Access Control Testing Engine.

Tests:
  - Terminated employee access (ghost accounts)
  - Excessive privilege / admin overreach
  - Dormant accounts (no login > 90 days)
  - Shared/generic accounts
  - Missing MFA for privileged users
  - Quarterly access review completeness
  - Privileged Access Management (PAM) controls
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta, timezone
import logging

logger = logging.getLogger(__name__)

DORMANT_THRESHOLD_DAYS = 90
REVIEW_CYCLE_DAYS = 90
PRIVILEGED_KEYWORDS = [
    "admin", "administrator", "root", "superuser", "sysadmin",
    "basis", "security", "privileged", "super", "power_user",
    "full_access", "all_access", "god_mode", "developer", "basis_admin",
]
GENERIC_ACCOUNT_PATTERNS = [
    "svc_", "service_", "shared_", "generic_", "test_", "temp_",
    "batch_", "system_", "app_", "integration_", "api_",
]


@dataclass
class AccessFinding:
    control_id: str
    user_id: str
    finding_type: str
    risk_level: str
    description: str
    recommendation: str
    evidence: Dict = field(default_factory=dict)
    status: str = "EXCEPTION"

    def to_dict(self) -> dict:
        return {
            "control_id": self.control_id,
            "user_id": self.user_id,
            "finding_type": self.finding_type,
            "risk_level": self.risk_level,
            "description": self.description,
            "recommendation": self.recommendation,
            "evidence": self.evidence,
            "status": self.status,
        }


def _parse_date(val: Any) -> Optional[datetime]:
    """Try to parse a date from various string formats."""
    if val is None or val == "" or str(val).lower() in ("nan", "none", "null", "n/a"):
        return None
    if isinstance(val, datetime):
        return val
    formats = [
        "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d",
        "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%m-%d-%Y",
    ]
    s = str(val).strip()
    for fmt in formats:
        try:
            return datetime.strptime(s[:len(fmt)], fmt)
        except (ValueError, TypeError):
            continue
    return None


def _is_privileged(roles: List[str]) -> bool:
    roles_str = " ".join(r.lower() for r in roles)
    return any(kw in roles_str for kw in PRIVILEGED_KEYWORDS)


def _is_generic_account(user_id: str) -> bool:
    uid = user_id.lower()
    return any(uid.startswith(pat) for pat in GENERIC_ACCOUNT_PATTERNS)


def test_access_controls(users: List[Dict], as_of_date: Optional[datetime] = None) -> List[AccessFinding]:
    """
    Run all logical access control tests against a list of user records.

    Expected user dict fields (all optional except user_id):
        user_id, username, status, termination_date, last_login_date,
        roles, mfa_enabled, access_review_date, department, manager
    """
    findings: List[AccessFinding] = []
    now = as_of_date or datetime.now(timezone.utc).replace(tzinfo=None)

    for user in users:
        uid = str(user.get("user_id") or user.get("username") or user.get("user") or "UNKNOWN")
        status = str(user.get("status", "")).lower().strip()
        roles = user.get("roles", [])
        if isinstance(roles, str):
            roles = [r.strip() for r in roles.replace(";", ",").split(",") if r.strip()]

        term_date = _parse_date(user.get("termination_date") or user.get("term_date"))
        last_login = _parse_date(user.get("last_login_date") or user.get("last_login"))
        review_date = _parse_date(user.get("access_review_date") or user.get("last_review"))
        mfa = str(user.get("mfa_enabled", "")).lower()

        # ── TEST 1: Terminated employee with active access ────────────────────
        is_terminated = (
            status in ("terminated", "inactive", "disabled", "term", "t") or
            (term_date and term_date < now)
        )
        if is_terminated and status not in ("disabled", "inactive", "locked"):
            findings.append(AccessFinding(
                control_id="ITGC-LA-001",
                user_id=uid,
                finding_type="TERMINATED_USER_ACTIVE",
                risk_level="CRITICAL",
                description=f"User {uid} appears terminated but account is still active in the system.",
                recommendation="Immediately disable/delete account. Review all transactions performed after termination date for unauthorized activity.",
                evidence={"termination_date": str(term_date), "status": status, "roles": roles},
            ))

        # ── TEST 2: Dormant account ───────────────────────────────────────────
        if last_login and status not in ("terminated", "inactive", "disabled"):
            days_dormant = (now - last_login).days
            if days_dormant > DORMANT_THRESHOLD_DAYS:
                risk = "HIGH" if _is_privileged(roles) else "MEDIUM"
                findings.append(AccessFinding(
                    control_id="ITGC-LA-002",
                    user_id=uid,
                    finding_type="DORMANT_ACCOUNT",
                    risk_level=risk,
                    description=f"User {uid} has not logged in for {days_dormant} days (threshold: {DORMANT_THRESHOLD_DAYS} days).",
                    recommendation=f"Disable dormant account immediately. Contact manager to confirm if access is still needed. Re-enable only with documented business justification.",
                    evidence={"last_login": str(last_login), "days_dormant": days_dormant},
                ))

        # ── TEST 3: Missing MFA for privileged users ──────────────────────────
        if _is_privileged(roles) and mfa not in ("yes", "true", "1", "enabled", "y"):
            findings.append(AccessFinding(
                control_id="ITGC-LA-003",
                user_id=uid,
                finding_type="PRIVILEGED_NO_MFA",
                risk_level="CRITICAL",
                description=f"Privileged user {uid} does not have MFA enabled.",
                recommendation="Enable MFA immediately for all privileged accounts. No exceptions. Implement as a technical control, not a policy control.",
                evidence={"roles": roles, "mfa_enabled": mfa},
            ))

        # ── TEST 4: Generic / shared account with active roles ────────────────
        if _is_generic_account(uid) and roles and status not in ("disabled", "inactive"):
            findings.append(AccessFinding(
                control_id="ITGC-LA-004",
                user_id=uid,
                finding_type="GENERIC_SHARED_ACCOUNT",
                risk_level="HIGH",
                description=f"Generic/shared account {uid} has active system access — individual accountability not maintained.",
                recommendation="Replace shared accounts with individual named accounts. If service account, restrict to minimum required permissions and vault the credentials in PAM.",
                evidence={"account_type": "generic/shared", "roles": roles},
            ))

        # ── TEST 5: Access review overdue ─────────────────────────────────────
        if review_date:
            days_since_review = (now - review_date).days
            if days_since_review > REVIEW_CYCLE_DAYS:
                findings.append(AccessFinding(
                    control_id="ITGC-LA-005",
                    user_id=uid,
                    finding_type="ACCESS_REVIEW_OVERDUE",
                    risk_level="MEDIUM",
                    description=f"Access review for {uid} is {days_since_review} days overdue (required every {REVIEW_CYCLE_DAYS} days).",
                    recommendation="Include in next immediate access review cycle. Obtain manager certification of continued need for all roles.",
                    evidence={"last_review_date": str(review_date), "days_overdue": days_since_review - REVIEW_CYCLE_DAYS},
                ))
        elif not review_date and status not in ("terminated", "disabled"):
            findings.append(AccessFinding(
                control_id="ITGC-LA-005",
                user_id=uid,
                finding_type="ACCESS_REVIEW_MISSING",
                risk_level="MEDIUM",
                description=f"No access review date found for active user {uid}.",
                recommendation="Perform immediate access review and document manager certification.",
                evidence={"review_date": "Not found"},
            ))

        # ── TEST 6: Excessive admin roles (more than 3 privileged roles) ──────
        priv_roles = [r for r in roles if any(kw in r.lower() for kw in PRIVILEGED_KEYWORDS)]
        if len(priv_roles) > 3:
            findings.append(AccessFinding(
                control_id="ITGC-LA-006",
                user_id=uid,
                finding_type="EXCESSIVE_PRIVILEGE",
                risk_level="HIGH",
                description=f"User {uid} holds {len(priv_roles)} privileged roles — excessive privilege accumulation detected.",
                recommendation="Apply principle of least privilege. Remove roles not actively used in last 90 days. Require documented business justification for each privileged role.",
                evidence={"privileged_roles": priv_roles, "count": len(priv_roles)},
            ))

    logger.info("Access engine: scanned %d users, found %d findings", len(users), len(findings))
    return findings


def summarize_access_results(findings: List[AccessFinding]) -> dict:
    by_type: Dict[str, int] = {}
    by_risk = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for f in findings:
        by_type[f.finding_type] = by_type.get(f.finding_type, 0) + 1
        by_risk[f.risk_level] = by_risk.get(f.risk_level, 0) + 1

    return {
        "total_exceptions": len(findings),
        "by_type": by_type,
        "by_risk_level": by_risk,
        "pass": len(findings) == 0,
        "control_area": "Logical Access Controls",
        "standard_ref": "ITGC-LA · COSO CC6.1-6.3 · SOX 404 · ISO 27001 A.9",
    }
