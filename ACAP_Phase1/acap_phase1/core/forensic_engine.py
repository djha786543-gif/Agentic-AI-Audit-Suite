"""
core/forensic_engine.py
───────────────────────
Layer 2 — The Forensic Reasoning Layer (AI-on-AI Auditing)

Two capabilities:
  1. INTEGRITY CHECKER:  Cross-references AI-generated Executive Summaries
                         against raw JSON/database data to flag hallucinations,
                         math errors, or inconsistencies.
  2. AUDITOR REASONING:  For every flagged risk, generates a human-readable
                         'Auditor Reasoning' field that explains the specific
                         SOX control violation.

Usage:
    from core.forensic_engine import ForensicEngine
    engine = ForensicEngine()
    result = engine.verify_summary(summary_data, raw_records)
    reason = engine.generate_reasoning(event, control_type)
"""

import hashlib
import json
import logging
import math
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ─── SOX Control Violation Templates ─────────────────────────────────────────
SOX_VIOLATION_TEMPLATES = {
    "preventative_bypass": (
        "Bypass of Preventative Control: Server-side validation failed to trap "
        "{event_detail}. The control designed to prevent {risk_type} did not "
        "operate effectively during the period under review."
    ),
    "detective_failure": (
        "Detective Control Delay: The anomaly '{event_detail}' was not flagged "
        "within the expected detection window. Delayed detection increases "
        "exposure to {risk_type}."
    ),
    "segregation_of_duties": (
        "Segregation of Duties Violation: User '{user}' performed both "
        "{action_1} and {action_2}, violating the dual-authorization requirement "
        "under SOX Section 404."
    ),
    "access_control": (
        "Unauthorized Access Pattern: {user} accessed {resource} with "
        "privilege level '{access_level}' which exceeds the minimum necessary "
        "for their role assignment."
    ),
    "boundary_injection": (
        "Boundary-Value Injection: The value '{value}' falls at a system "
        "boundary threshold, suggesting potential adversarial testing or "
        "systematic manipulation of input validation."
    ),
    "data_integrity": (
        "Data Integrity Failure: Hash mismatch detected for record {record_id}. "
        "The stored evidence may have been altered after initial vault ingestion, "
        "compromising chain-of-custody."
    ),
    "negative_amount": (
        "Negative Amount Anomaly: Transaction value of {amount} represents a "
        "potential reversal or credit manipulation. Under SOX requirements, "
        "negative values in {context} require dual-approval authorization."
    ),
}


class IntegrityCheckResult:
    """Result of an AI-on-AI integrity verification."""

    def __init__(self):
        self.is_valid: bool = True
        self.discrepancies: List[Dict[str, Any]] = []
        self.math_errors: List[Dict[str, Any]] = []
        self.hallucinations: List[Dict[str, Any]] = []
        self.warnings: List[str] = []
        self.checked_at: str = datetime.now(timezone.utc).isoformat()
        self.confidence_score: float = 100.0

    def add_discrepancy(self, field: str, summary_value: Any, actual_value: Any, severity: str = "high"):
        self.is_valid = False
        self.discrepancies.append({
            "field": field,
            "summary_value": summary_value,
            "actual_value": actual_value,
            "severity": severity,
            "type": "discrepancy",
        })
        self._degrade_confidence(severity)

    def add_math_error(self, calculation: str, expected: Any, actual: Any, severity: str = "critical"):
        self.is_valid = False
        self.math_errors.append({
            "calculation": calculation,
            "expected": expected,
            "actual": actual,
            "severity": severity,
            "type": "math_error",
        })
        self._degrade_confidence(severity)

    def add_hallucination(self, claim: str, evidence: str, severity: str = "critical"):
        self.is_valid = False
        self.hallucinations.append({
            "claim": claim,
            "actual_evidence": evidence,
            "severity": severity,
            "type": "hallucination",
        })
        self._degrade_confidence(severity)

    def add_warning(self, message: str):
        self.warnings.append(message)
        self.confidence_score = max(0, self.confidence_score - 2)

    def _degrade_confidence(self, severity: str):
        degradation = {"critical": 25, "high": 15, "medium": 8, "low": 3}
        self.confidence_score = max(0, self.confidence_score - degradation.get(severity, 5))

    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "confidence_score": round(self.confidence_score, 1),
            "discrepancies": self.discrepancies,
            "math_errors": self.math_errors,
            "hallucinations": self.hallucinations,
            "warnings": self.warnings,
            "total_issues": len(self.discrepancies) + len(self.math_errors) + len(self.hallucinations),
            "checked_at": self.checked_at,
        }


class ForensicEngine:
    """
    The Forensic Reasoning Layer — AI-on-AI Auditing.

    Verifies AI-generated summaries against raw data and generates
    human-readable SOX violation explanations.
    """

    def __init__(self):
        self._verification_count = 0

    # ──────────────────────────────────────────────────────────────────────
    # INTEGRITY CHECKER
    # ──────────────────────────────────────────────────────────────────────

    def verify_summary(
        self,
        summary: Dict[str, Any],
        raw_records: List[Dict[str, Any]],
    ) -> IntegrityCheckResult:
        """
        Cross-reference an AI-generated Executive Summary against raw data.

        Checks for:
          1. Count mismatches (summary says N records, but actually M)
          2. Math errors (totals don't add up)
          3. Hallucinated findings (claims not supported by data)
          4. Missing critical data (raw data exists but summary ignores it)

        Args:
            summary:     The AI-generated summary dict
            raw_records: The raw event records from database/JSON

        Returns:
            IntegrityCheckResult with all discrepancies documented
        """
        result = IntegrityCheckResult()
        self._verification_count += 1

        # Check 1: Record count accuracy
        self._check_record_counts(summary, raw_records, result)

        # Check 2: Financial totals accuracy
        self._check_financial_totals(summary, raw_records, result)

        # Check 3: Priority distribution accuracy
        self._check_priority_distribution(summary, raw_records, result)

        # Check 4: Source system references
        self._check_source_references(summary, raw_records, result)

        # Check 5: Hash integrity claims
        self._check_hash_claims(summary, raw_records, result)

        # Check 6: Temporal consistency
        self._check_temporal_claims(summary, raw_records, result)

        logger.info(
            "forensic.verify_complete  valid=%s  confidence=%.1f  issues=%d",
            result.is_valid, result.confidence_score,
            len(result.discrepancies) + len(result.math_errors) + len(result.hallucinations),
        )

        return result

    def verify_finding_against_data(
        self,
        finding: Dict[str, Any],
        raw_events: List[Dict[str, Any]],
    ) -> IntegrityCheckResult:
        """
        Verify a single finding against its source events.
        Ensures the finding's claims are supported by evidence.
        """
        result = IntegrityCheckResult()

        # Verify occurrence count
        claimed_count = finding.get("occurrence_count", 0)
        event_ids = finding.get("raw_event_ids", [])
        if claimed_count != len(event_ids):
            result.add_discrepancy(
                field="occurrence_count",
                summary_value=claimed_count,
                actual_value=len(event_ids),
                severity="high",
            )

        # Verify financial impact
        claimed_impact = finding.get("financial_impact", 0)
        actual_impact = sum(self._extract_amount(e) for e in raw_events)
        if abs(claimed_impact - actual_impact) > 0.01:
            tolerance = max(1.0, actual_impact * 0.01)  # 1% tolerance
            if abs(claimed_impact - actual_impact) > tolerance:
                result.add_math_error(
                    calculation="financial_impact_sum",
                    expected=actual_impact,
                    actual=claimed_impact,
                    severity="critical" if abs(claimed_impact - actual_impact) > 1000 else "high",
                )

        # Verify risk score is within valid range
        risk_score = finding.get("risk_score", -1)
        if risk_score < 0 or risk_score > 100:
            result.add_discrepancy(
                field="risk_score",
                summary_value=risk_score,
                actual_value="must be 0-100",
                severity="critical",
            )

        return result

    # ──────────────────────────────────────────────────────────────────────
    # INTEGRITY CHECK SUBROUTINES
    # ──────────────────────────────────────────────────────────────────────

    def _check_record_counts(
        self, summary: Dict, raw_records: List[Dict], result: IntegrityCheckResult
    ):
        """Verify that claimed record counts match actual data."""
        claimed_total = summary.get("total_raw_events") or summary.get("total_records")
        if claimed_total is not None:
            actual_total = len(raw_records)
            if claimed_total != actual_total:
                result.add_discrepancy(
                    field="total_raw_events",
                    summary_value=claimed_total,
                    actual_value=actual_total,
                    severity="critical" if abs(claimed_total - actual_total) > 10 else "high",
                )

        # Check sub-counts
        for key in ["critical_findings", "high_findings", "auto_cleared", "systemic_groups"]:
            claimed = summary.get(key)
            if claimed is not None and claimed < 0:
                result.add_discrepancy(
                    field=key,
                    summary_value=claimed,
                    actual_value="must be >= 0",
                    severity="medium",
                )

    def _check_financial_totals(
        self, summary: Dict, raw_records: List[Dict], result: IntegrityCheckResult
    ):
        """Verify that financial totals are mathematically correct."""
        claimed_total = summary.get("total_financial_impact")
        if claimed_total is not None:
            actual_total = sum(self._extract_amount(r) for r in raw_records)
            # Allow up to 1% tolerance for floating point and materiality filtering
            if actual_total > 0:
                diff_pct = abs(claimed_total - actual_total) / actual_total * 100
                if diff_pct > 5 and abs(claimed_total - actual_total) > 100:
                    result.add_math_error(
                        calculation="total_financial_impact",
                        expected=round(actual_total, 2),
                        actual=round(claimed_total, 2),
                        severity="critical",
                    )
                elif diff_pct > 1:
                    result.add_warning(
                        f"Financial total variance of {diff_pct:.1f}% detected "
                        f"(claimed ${claimed_total:,.2f} vs actual ${actual_total:,.2f}). "
                        f"This may be due to materiality filtering."
                    )

    def _check_priority_distribution(
        self, summary: Dict, raw_records: List[Dict], result: IntegrityCheckResult
    ):
        """Verify priority counts add up correctly."""
        priority_keys = ["critical_findings", "high_findings", "medium_findings", "low_findings"]
        claimed_counts = {k: summary.get(k, 0) for k in priority_keys}
        total_findings = sum(claimed_counts.values())

        auto_cleared = summary.get("auto_cleared", 0)
        total_raw = summary.get("total_raw_events", 0)

        # The sum of findings + auto_cleared should relate to total_raw
        if total_raw > 0 and (total_findings + auto_cleared) > total_raw:
            result.add_warning(
                f"Priority distribution anomaly: {total_findings} findings + "
                f"{auto_cleared} auto-cleared = {total_findings + auto_cleared}, "
                f"but only {total_raw} raw events reported."
            )

    def _check_source_references(
        self, summary: Dict, raw_records: List[Dict], result: IntegrityCheckResult
    ):
        """Check that source systems referenced in summary actually exist in data."""
        actual_sources = {str(r.get("source_system", "")).lower() for r in raw_records}

        # If summary mentions specific sources, verify they exist
        findings = summary.get("findings", [])
        if isinstance(findings, list):
            for finding in findings:
                category = str(finding.get("category", ""))
                parts = category.split("|")
                if parts:
                    ref_source = parts[0].strip().lower()
                    if ref_source and ref_source not in actual_sources and ref_source != "unknown":
                        result.add_hallucination(
                            claim=f"Finding references source '{ref_source}'",
                            evidence=f"Actual sources in data: {', '.join(actual_sources)}",
                            severity="high",
                        )

    def _check_hash_claims(
        self, summary: Dict, raw_records: List[Dict], result: IntegrityCheckResult
    ):
        """Verify any hash-related claims in the summary."""
        claimed_verified = summary.get("hash_verified_count")
        if claimed_verified is not None:
            actual_verified = sum(
                1 for r in raw_records
                if r.get("hash_verified") is True
            )
            if claimed_verified != actual_verified:
                result.add_discrepancy(
                    field="hash_verified_count",
                    summary_value=claimed_verified,
                    actual_value=actual_verified,
                    severity="critical",
                )

    def _check_temporal_claims(
        self, summary: Dict, raw_records: List[Dict], result: IntegrityCheckResult
    ):
        """Verify temporal claims (date ranges, recency claims)."""
        claimed_start = summary.get("period_start")
        claimed_end = summary.get("period_end")

        if claimed_start and claimed_end and raw_records:
            timestamps = []
            for r in raw_records:
                ts = r.get("timestamp") or r.get("recorded_at")
                if ts:
                    if isinstance(ts, str):
                        try:
                            timestamps.append(datetime.fromisoformat(ts.replace("Z", "+00:00")))
                        except ValueError:
                            pass
                    elif isinstance(ts, datetime):
                        timestamps.append(ts)

            if timestamps:
                actual_start = min(timestamps)
                actual_end = max(timestamps)
                try:
                    cs = datetime.fromisoformat(str(claimed_start).replace("Z", "+00:00"))
                    ce = datetime.fromisoformat(str(claimed_end).replace("Z", "+00:00"))
                    if cs > actual_start or ce < actual_end:
                        result.add_warning(
                            f"Temporal range in summary ({claimed_start} to {claimed_end}) "
                            f"does not fully cover actual data range "
                            f"({actual_start.isoformat()} to {actual_end.isoformat()})."
                        )
                except (ValueError, TypeError):
                    result.add_warning("Unable to parse temporal claims for verification.")

    # ──────────────────────────────────────────────────────────────────────
    # AUDITOR REASONING GENERATOR
    # ──────────────────────────────────────────────────────────────────────

    def generate_reasoning(
        self,
        event: Dict[str, Any],
        control_type: str = "detective",
        financial_impact: float = 0.0,
        context: str = "",
    ) -> str:
        """
        Generate a human-readable 'Auditor Reasoning' for a flagged risk.

        This explains the specific SOX control violation in language
        suitable for an audit report.
        """
        reasons = []

        event_type = str(event.get("event_type", "unknown"))
        source = str(event.get("source_system", "unknown"))
        log_data = str(event.get("log_data", ""))

        # Primary reasoning based on control type
        if control_type == "preventative":
            reasons.append(SOX_VIOLATION_TEMPLATES["preventative_bypass"].format(
                event_detail=event_type,
                risk_type="unauthorized transactions",
            ))
        elif control_type == "detective":
            reasons.append(SOX_VIOLATION_TEMPLATES["detective_failure"].format(
                event_detail=event_type,
                risk_type="undetected anomalies",
            ))

        # Check for negative amounts
        amounts = re.findall(r'-\$?([\d,]+\.?\d*)', log_data)
        if amounts:
            reasons.append(SOX_VIOLATION_TEMPLATES["negative_amount"].format(
                amount=f"-${amounts[0]}",
                context=context or source,
            ))

        # Check for boundary values
        all_amounts = re.findall(r'\$?([\d,]+\.?\d*)', log_data)
        for amt_str in all_amounts:
            try:
                val = float(amt_str.replace(",", ""))
                if val in (0, 0.01, 999.99, 9999.99, 99999.99):
                    reasons.append(SOX_VIOLATION_TEMPLATES["boundary_injection"].format(
                        value=f"${val:,.2f}",
                    ))
                    break
            except (ValueError, TypeError):
                continue

        # Check for access control issues
        user = event.get("user") or event.get("performed_by")
        access_level = event.get("access_level")
        if user and access_level:
            reasons.append(SOX_VIOLATION_TEMPLATES["access_control"].format(
                user=user,
                resource=source,
                access_level=access_level,
            ))

        # Check for hash integrity
        if event.get("hash_verified") is False:
            reasons.append(SOX_VIOLATION_TEMPLATES["data_integrity"].format(
                record_id=event.get("id", "unknown"),
            ))

        # Financial impact context
        if financial_impact >= 10000:
            reasons.append(
                f"MATERIAL IMPACT: ${financial_impact:,.2f} exceeds materiality threshold. "
                f"This finding requires management attention per SOX Section 302 certification requirements."
            )

        if not reasons:
            reasons.append(
                f"General Monitoring Alert: '{event_type}' event from '{source}' "
                f"flagged for review. No specific SOX violation pattern matched, "
                f"but the event warrants auditor assessment."
            )

        return " | ".join(reasons)

    def generate_executive_summary(
        self,
        findings: List[Dict[str, Any]],
        summary_stats: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate a verified executive summary from processed findings.
        This summary is self-verified against the source data.
        """
        critical = [f for f in findings if f.get("priority") == "Critical"]
        high = [f for f in findings if f.get("priority") == "High"]
        systemic = [f for f in findings if f.get("is_systemic")]

        total_impact = sum(f.get("financial_impact", 0) for f in findings)
        max_risk = max((f.get("risk_score", 0) for f in findings), default=0)

        executive_summary = {
            "headline": self._generate_headline(critical, high, total_impact),
            "risk_posture": "Critical" if critical else ("Elevated" if high else "Stable"),
            "critical_count": len(critical),
            "high_count": len(high),
            "systemic_count": len(systemic),
            "total_financial_exposure": round(total_impact, 2),
            "highest_risk_score": round(max_risk, 1),
            "top_findings": [
                {
                    "finding_id": f.get("finding_id"),
                    "description": f.get("description", "")[:200],
                    "risk_score": f.get("risk_score"),
                    "priority": f.get("priority"),
                    "financial_impact": f.get("financial_impact"),
                }
                for f in findings[:5]   # top 5 by risk score
            ],
            "recommendations": self._generate_recommendations(critical, high, systemic),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "verification_status": "self_verified",
        }

        # Self-verify the summary we just generated
        verification = self.verify_summary(
            {**executive_summary, **summary_stats},
            findings,
        )
        executive_summary["integrity_check"] = verification.to_dict()

        return executive_summary

    def _generate_headline(
        self, critical: List[Dict], high: List[Dict], total_impact: float
    ) -> str:
        """Generate the executive headline."""
        if critical:
            return (
                f"CRITICAL: {len(critical)} critical finding(s) requiring "
                f"immediate attention. Total financial exposure: ${total_impact:,.2f}."
            )
        elif high:
            return (
                f"ELEVATED RISK: {len(high)} high-priority finding(s) identified. "
                f"Total financial exposure: ${total_impact:,.2f}."
            )
        else:
            return (
                f"STABLE: No critical or high-priority findings. "
                f"Total reviewed financial exposure: ${total_impact:,.2f}."
            )

    def _generate_recommendations(
        self,
        critical: List[Dict],
        high: List[Dict],
        systemic: List[Dict],
    ) -> List[str]:
        """Generate actionable recommendations."""
        recs = []

        if critical:
            recs.append(
                "IMMEDIATE: Escalate critical findings to the Audit Committee. "
                "Initiate root-cause analysis within 24 hours."
            )

        if systemic:
            recs.append(
                "SYSTEMIC: Engage IT Controls team to investigate systematic "
                "logic gaps in source systems. Consider temporary compensating controls."
            )

        if high:
            recs.append(
                "PRIORITY: Schedule management review of high-priority findings "
                "within the current reporting period."
            )

        if not recs:
            recs.append(
                "MAINTAIN: Continue current monitoring cadence. No escalation required."
            )

        return recs

    # ──────────────────────────────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_amount(event: Dict[str, Any]) -> float:
        """Extract financial amount from an event record."""
        amount_fields = ["amount", "transaction_value", "financial_impact", "value", "total"]
        for field in amount_fields:
            val = event.get(field)
            if val is not None:
                try:
                    return abs(float(val))
                except (ValueError, TypeError):
                    continue

        log_data = str(event.get("log_data", ""))
        amounts = re.findall(r'\$?([\d,]+\.?\d*)', log_data)
        if amounts:
            try:
                return abs(float(amounts[0].replace(",", "")))
            except (ValueError, TypeError):
                pass

        return 0.0
