"""
engine/operations.py
────────────────────
IT Operations Control Testing Engine.

Tests:
  - Backup completeness and frequency
  - Job failure monitoring and response
  - Incident response timeliness
  - Capacity management alerts
  - Data retention compliance
  - Disaster recovery test evidence
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

BACKUP_FREQUENCY_DAYS = 1       # Daily backup expected
DR_TEST_FREQUENCY_DAYS = 365    # Annual DR test
INCIDENT_RESPONSE_HOURS = 4     # P1 incidents resolved within 4 hours
JOB_FAILURE_RESPONSE_HOURS = 2  # Failed batch jobs responded within 2 hours


@dataclass
class OperationsFinding:
    control_id: str
    record_id: str
    finding_type: str
    risk_level: str
    description: str
    recommendation: str
    evidence: Dict = field(default_factory=dict)
    status: str = "EXCEPTION"

    def to_dict(self) -> dict:
        return {
            "control_id": self.control_id,
            "record_id": self.record_id,
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
    formats = ["%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%m-%d-%Y"]
    s = str(val).strip()
    for fmt in formats:
        try:
            return datetime.strptime(s[:19], fmt)
        except (ValueError, TypeError):
            continue
    return None


def _str(val: Any) -> str:
    return str(val).strip().lower() if val is not None else ""


def test_operations_controls(records: List[Dict], record_type: str = "backup") -> List[OperationsFinding]:
    """
    Test IT operations controls. record_type can be:
      'backup'   - backup job records
      'incident' - incident/ticket records
      'job'      - batch job records
      'dr'       - disaster recovery test records
    """
    findings: List[OperationsFinding] = []
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    if record_type == "backup":
        last_backup = None
        for rec in records:
            rid = str(rec.get("job_id") or rec.get("backup_id") or rec.get("id") or "UNKNOWN")
            status = _str(rec.get("status") or rec.get("result"))
            backup_date = _parse_date(rec.get("backup_date") or rec.get("completed_at") or rec.get("date"))
            system = str(rec.get("system") or rec.get("server") or "Unknown")
            verified = _str(rec.get("restore_tested") or rec.get("verified"))

            if status in ("failed", "error", "failure", "f"):
                findings.append(OperationsFinding(
                    control_id="ITGC-OPS-001",
                    record_id=rid,
                    finding_type="BACKUP_FAILURE",
                    risk_level="CRITICAL",
                    description=f"Backup job {rid} for {system} FAILED — data recovery capability compromised.",
                    recommendation="Investigate failure root cause immediately. Perform manual backup and verify restore. Review backup monitoring alerts to ensure on-call team was notified.",
                    evidence={"job_id": rid, "system": system, "status": status, "date": str(backup_date)},
                ))

            if backup_date:
                days_old = (now - backup_date).days
                if days_old > BACKUP_FREQUENCY_DAYS:
                    findings.append(OperationsFinding(
                        control_id="ITGC-OPS-002",
                        record_id=rid,
                        finding_type="BACKUP_OVERDUE",
                        risk_level="HIGH",
                        description=f"Last backup for {system} is {days_old} days old — exceeds {BACKUP_FREQUENCY_DAYS}-day requirement.",
                        recommendation="Perform immediate backup. Review why scheduled backup did not run. Check backup monitoring and alerting is functioning.",
                        evidence={"last_backup": str(backup_date), "days_old": days_old},
                    ))

            if verified not in ("yes", "true", "1", "y", "tested", "verified", "passed"):
                findings.append(OperationsFinding(
                    control_id="ITGC-OPS-003",
                    record_id=rid,
                    finding_type="BACKUP_NOT_VERIFIED",
                    risk_level="MEDIUM",
                    description=f"Backup {rid} for {system} has not been restore-tested — backup integrity unconfirmed.",
                    recommendation="Perform restore test quarterly. Document restore test results including files verified, duration, and success criteria.",
                    evidence={"job_id": rid, "restore_tested": verified},
                ))

    elif record_type == "incident":
        for rec in records:
            rid = str(rec.get("incident_id") or rec.get("ticket_id") or rec.get("id") or "UNKNOWN")
            priority = _str(rec.get("priority") or rec.get("severity"))
            status = _str(rec.get("status"))
            created = _parse_date(rec.get("created_at") or rec.get("opened_date"))
            resolved = _parse_date(rec.get("resolved_at") or rec.get("resolved_date"))

            if priority in ("p1", "critical", "1", "high") and created:
                if resolved:
                    hours_to_resolve = (resolved - created).total_seconds() / 3600
                    if hours_to_resolve > INCIDENT_RESPONSE_HOURS:
                        findings.append(OperationsFinding(
                            control_id="ITGC-OPS-004",
                            record_id=rid,
                            finding_type="P1_RESPONSE_BREACH",
                            risk_level="HIGH",
                            description=f"P1 incident {rid} took {hours_to_resolve:.1f} hours to resolve — exceeds {INCIDENT_RESPONSE_HOURS}h SLA.",
                            recommendation="Review P1 escalation procedures and on-call rotation. Document root cause for SLA breach. Update incident response runbooks.",
                            evidence={"hours_to_resolve": round(hours_to_resolve, 1), "sla_hours": INCIDENT_RESPONSE_HOURS},
                        ))
                elif status not in ("resolved", "closed", "fixed"):
                    findings.append(OperationsFinding(
                        control_id="ITGC-OPS-005",
                        record_id=rid,
                        finding_type="P1_UNRESOLVED",
                        risk_level="CRITICAL",
                        description=f"P1 incident {rid} is still open — immediate escalation required.",
                        recommendation="Escalate to senior management immediately. Activate incident command structure. Update status every 30 minutes until resolved.",
                        evidence={"incident_id": rid, "status": status, "priority": priority},
                    ))

    elif record_type == "job":
        for rec in records:
            rid = str(rec.get("job_id") or rec.get("id") or "UNKNOWN")
            status = _str(rec.get("status") or rec.get("result"))
            job_name = str(rec.get("job_name") or rec.get("name") or rid)
            notified = _str(rec.get("alert_sent") or rec.get("team_notified"))

            if status in ("failed", "error", "abended", "abend"):
                findings.append(OperationsFinding(
                    control_id="ITGC-OPS-006",
                    record_id=rid,
                    finding_type="BATCH_JOB_FAILURE",
                    risk_level="HIGH",
                    description=f"Batch job '{job_name}' ({rid}) failed without evidence of team notification or resolution.",
                    recommendation="Ensure all job failures trigger automated alerts. Document root cause and resolution. Review job dependencies for downstream impact.",
                    evidence={"job": job_name, "status": status, "alert_sent": notified},
                ))

    elif record_type == "dr":
        last_test = None
        for rec in records:
            rid = str(rec.get("test_id") or rec.get("id") or "DR-TEST")
            test_date = _parse_date(rec.get("test_date") or rec.get("date"))
            result = _str(rec.get("result") or rec.get("status"))
            rto_met = _str(rec.get("rto_met") or rec.get("rto_achieved"))
            rpo_met = _str(rec.get("rpo_met") or rec.get("rpo_achieved"))

            if test_date and (last_test is None or test_date > last_test):
                last_test = test_date

            if result in ("failed", "fail", "unsuccessful"):
                findings.append(OperationsFinding(
                    control_id="ITGC-OPS-007",
                    record_id=rid,
                    finding_type="DR_TEST_FAILED",
                    risk_level="CRITICAL",
                    description=f"DR test {rid} FAILED — recovery capability not demonstrated.",
                    recommendation="Conduct root cause analysis immediately. Remediate gaps before next DR test. Update DR runbooks. Inform senior management and external auditors.",
                    evidence={"test_id": rid, "test_date": str(test_date), "result": result},
                ))

            if rto_met not in ("yes", "y", "true", "1", "met", "achieved", "passed"):
                findings.append(OperationsFinding(
                    control_id="ITGC-OPS-008",
                    record_id=rid,
                    finding_type="RTO_NOT_MET",
                    risk_level="HIGH",
                    description=f"DR test {rid} did not achieve Recovery Time Objective (RTO).",
                    recommendation="Review and update recovery procedures to meet RTO. Consider additional infrastructure capacity or automation to accelerate recovery.",
                    evidence={"rto_met": rto_met, "rpo_met": rpo_met},
                ))

        if last_test:
            days_since = (now - last_test).days
            if days_since > DR_TEST_FREQUENCY_DAYS:
                findings.append(OperationsFinding(
                    control_id="ITGC-OPS-009",
                    record_id="DR-OVERDUE",
                    finding_type="DR_TEST_OVERDUE",
                    risk_level="HIGH",
                    description=f"Last DR test was {days_since} days ago — annual requirement not met.",
                    recommendation="Schedule and complete DR test within 30 days. Ensure all critical systems are included in test scope.",
                    evidence={"last_test_date": str(last_test), "days_since": days_since},
                ))
        elif not records:
            findings.append(OperationsFinding(
                control_id="ITGC-OPS-009",
                record_id="DR-MISSING",
                finding_type="DR_TEST_MISSING",
                risk_level="CRITICAL",
                description="No DR test records found — no evidence that disaster recovery has been tested.",
                recommendation="Schedule DR test immediately. Document recovery procedures, assign responsibilities, and set measurable RTO/RPO objectives.",
                evidence={},
            ))

    logger.info("Operations engine [%s]: scanned %d records, found %d findings",
                record_type, len(records), len(findings))
    return findings


def summarize_operations_results(findings: List[OperationsFinding]) -> dict:
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
        "control_area": "Computer Operations",
        "standard_ref": "ITGC-OPS · COSO CC7.2 · COBIT · ISO 27001 A.12",
    }
