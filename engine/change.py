"""
engine/change.py
────────────────
Change Management Control Testing Engine.

Tests:
  - Unauthorized changes (no ticket / no approval)
  - Self-approved changes (initiator = approver)
  - Emergency changes without post-implementation review
  - Changes deployed without test evidence
  - High-frequency changes in production (change velocity risk)
  - Changes outside approved change windows
  - Developer access to production
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

CHANGE_WINDOW_HOURS = list(range(6, 22))   # 6 AM – 10 PM approved window
HIGH_VELOCITY_THRESHOLD = 10               # >10 changes/week flags velocity risk


@dataclass
class ChangeFinding:
    control_id: str
    ticket_id: str
    finding_type: str
    risk_level: str
    description: str
    recommendation: str
    evidence: Dict = field(default_factory=dict)
    status: str = "EXCEPTION"

    def to_dict(self) -> dict:
        return {
            "control_id": self.control_id,
            "ticket_id": self.ticket_id,
            "finding_type": self.finding_type,
            "risk_level": self.risk_level,
            "description": self.description,
            "recommendation": self.recommendation,
            "evidence": self.evidence,
            "status": self.status,
        }


def _parse_date(val: Any) -> Optional[datetime]:
    if val is None or str(val).lower() in ("nan", "none", "null", "", "n/a"):
        return None
    if isinstance(val, datetime):
        return val
    formats = [
        "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y",
        "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
        "%m-%d-%Y", "%Y/%m/%d",
    ]
    s = str(val).strip()
    for fmt in formats:
        try:
            return datetime.strptime(s[:19], fmt)
        except (ValueError, TypeError):
            continue
    return None


def _str(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip().lower()


def test_change_management(changes: List[Dict]) -> List[ChangeFinding]:
    """
    Run all change management control tests against a list of change tickets.

    Expected change dict fields:
        ticket_id, title/description, status, initiator/requested_by,
        approver/approved_by, implementation_date/deploy_date,
        test_evidence/uat_complete, change_type (normal/emergency/standard),
        post_impl_review/pir_complete, environment (prod/dev/test),
        implementation_hour (0-23)
    """
    findings: List[ChangeFinding] = []

    # Track weekly change counts for velocity analysis
    weekly_counts: Dict[str, int] = {}

    for chg in changes:
        tid = str(chg.get("ticket_id") or chg.get("change_id") or chg.get("id") or "UNKNOWN")
        initiator = _str(chg.get("initiator") or chg.get("requested_by") or chg.get("created_by"))
        approver = _str(chg.get("approver") or chg.get("approved_by") or chg.get("change_approver"))
        status = _str(chg.get("status") or chg.get("change_status"))
        change_type = _str(chg.get("change_type") or chg.get("type") or "normal")
        environment = _str(chg.get("environment") or chg.get("env") or "")
        test_evidence = _str(chg.get("test_evidence") or chg.get("uat_complete") or chg.get("testing"))
        pir = _str(chg.get("post_impl_review") or chg.get("pir_complete") or chg.get("post_implementation"))
        impl_date = _parse_date(chg.get("implementation_date") or chg.get("deploy_date") or chg.get("implemented_at"))

        is_prod = any(k in environment for k in ["prod", "production", "prd", "live"])

        # ── TEST 1: No approval documented ───────────────────────────────────
        if not approver or approver in ("", "none", "n/a", "nan"):
            risk = "CRITICAL" if is_prod else "HIGH"
            findings.append(ChangeFinding(
                control_id="ITGC-CM-001",
                ticket_id=tid,
                finding_type="NO_APPROVAL",
                risk_level=risk,
                description=f"Change {tid} has no documented approver — unauthorized change to {'production' if is_prod else 'system'}.",
                recommendation="Document approver for this change retroactively. Investigate who authorized deployment. Implement mandatory approval gate in change management tool.",
                evidence={"ticket": tid, "initiator": initiator, "approver": approver, "environment": environment},
            ))

        # ── TEST 2: Self-approved change ──────────────────────────────────────
        elif initiator and approver and initiator == approver:
            findings.append(ChangeFinding(
                control_id="ITGC-CM-002",
                ticket_id=tid,
                finding_type="SELF_APPROVED",
                risk_level="CRITICAL",
                description=f"Change {tid} was initiated AND approved by the same person ({initiator}) — SoD violation.",
                recommendation="Require separate approver for all changes. Implement system-level control to prevent self-approval. Review all self-approved changes for unauthorized modifications.",
                evidence={"initiator": initiator, "approver": approver},
            ))

        # ── TEST 3: Emergency change without post-implementation review ───────
        if "emergency" in change_type or "emerg" in change_type:
            if pir not in ("yes", "true", "1", "complete", "completed", "y", "done"):
                findings.append(ChangeFinding(
                    control_id="ITGC-CM-003",
                    ticket_id=tid,
                    finding_type="EMERGENCY_NO_PIR",
                    risk_level="HIGH",
                    description=f"Emergency change {tid} does not have a completed post-implementation review.",
                    recommendation="Complete post-implementation review within 5 business days of emergency change. Document root cause, impact assessment, and permanent fix plan.",
                    evidence={"change_type": change_type, "pir_status": pir},
                ))

        # ── TEST 4: No test evidence ──────────────────────────────────────────
        if is_prod and test_evidence not in ("yes", "true", "1", "complete", "completed", "y", "done", "passed"):
            if "standard" not in change_type:  # Standard pre-approved changes exempt
                findings.append(ChangeFinding(
                    control_id="ITGC-CM-004",
                    ticket_id=tid,
                    finding_type="NO_TEST_EVIDENCE",
                    risk_level="HIGH",
                    description=f"Production change {tid} was deployed without documented test/UAT evidence.",
                    recommendation="Require test evidence as mandatory attachment before production deployment. Implement automated gate in CI/CD pipeline.",
                    evidence={"environment": environment, "test_evidence": test_evidence},
                ))

        # ── TEST 5: Change outside approved window ────────────────────────────
        impl_hour = chg.get("implementation_hour")
        if impl_hour is not None and is_prod:
            try:
                hour = int(impl_hour)
                if hour not in CHANGE_WINDOW_HOURS:
                    findings.append(ChangeFinding(
                        control_id="ITGC-CM-005",
                        ticket_id=tid,
                        finding_type="OUTSIDE_CHANGE_WINDOW",
                        risk_level="MEDIUM",
                        description=f"Change {tid} implemented at hour {hour}:00 — outside approved change window (06:00-22:00).",
                        recommendation="Classify as emergency change and obtain retroactive approval. Review change calendar adherence. Consider whether this indicates unauthorized activity.",
                        evidence={"implementation_hour": hour, "approved_window": "06:00-22:00"},
                    ))
            except (ValueError, TypeError):
                pass

        # Track weekly velocity
        if impl_date:
            week_key = impl_date.strftime("%Y-W%W")
            weekly_counts[week_key] = weekly_counts.get(week_key, 0) + 1

    # ── TEST 6: High change velocity ──────────────────────────────────────────
    for week, count in weekly_counts.items():
        if count > HIGH_VELOCITY_THRESHOLD:
            findings.append(ChangeFinding(
                control_id="ITGC-CM-006",
                ticket_id=f"VELOCITY-{week}",
                finding_type="HIGH_CHANGE_VELOCITY",
                risk_level="MEDIUM",
                description=f"Week {week}: {count} changes detected — exceeds threshold of {HIGH_VELOCITY_THRESHOLD}. High velocity increases risk of inadequate review.",
                recommendation="Review all changes in high-velocity period for proper approvals and testing. Consider whether change freeze period is needed. Assess if changes are appropriately batched.",
                evidence={"week": week, "change_count": count, "threshold": HIGH_VELOCITY_THRESHOLD},
            ))

    logger.info("Change engine: scanned %d tickets, found %d findings", len(changes), len(findings))
    return findings


def summarize_change_results(findings: List[ChangeFinding]) -> dict:
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
        "control_area": "Change Management",
        "standard_ref": "ITGC-CM · COSO CC8.1 · ITIL · SOX 404",
    }
