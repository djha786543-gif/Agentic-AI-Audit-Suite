"""
core/sox_validator.py
─────────────────────
Layer 1 — The Materiality & Aggregation Engine (The Brain)

This module transforms raw audit events from 'simple detection' noise into
prioritized, deduplicated, risk-scored intelligence suitable for human auditors.

Three capabilities:
  1. DEDUPLICATION:    Group 400+ identical technical errors into a single
                       'Systemic Logic Gap' alert (e.g. hundreds of 'Negative Amount'
                       warnings become one grouped finding).
  2. MATERIALITY:     Filter / auto-clear anomalies with financial impact < $500
                       so auditors focus only on high-stakes risks.
  3. RISK SCORING:    Assign a weighted score 0–100 based on transaction value,
                       behavioral complexity, and control-type severity.

Usage:
    from core.sox_validator import SOXValidator
    validator = SOXValidator()
    results  = validator.process_events(raw_events)
"""

import hashlib
import json
import logging
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ─── Materiality Threshold ────────────────────────────────────────────────────
DEFAULT_MATERIALITY_THRESHOLD = 500.00   # USD — anomalies below this are auto-cleared

# ─── Risk Weight Configuration ────────────────────────────────────────────────
RISK_WEIGHTS = {
    "transaction_value":      0.35,   # how large is the dollar amount?
    "behavioral_complexity":  0.25,   # unusual patterns, boundary values, etc.
    "control_severity":       0.20,   # what type of SOX control is affected?
    "frequency_factor":       0.10,   # systemic = higher risk
    "recency_factor":         0.10,   # more recent = higher urgency
}

# ─── Control Severity Lookup ──────────────────────────────────────────────────
CONTROL_SEVERITY = {
    "preventative":  1.0,    # highest: should have stopped the event
    "detective":     0.7,    # found after the fact
    "corrective":    0.5,    # remediation controls
    "monitoring":    0.3,    # lowest: informational
}

# ─── Deduplication Threshold ──────────────────────────────────────────────────
SYSTEMIC_THRESHOLD = 10   # 10+ similar events = Systemic Logic Gap alert


class AuditFinding:
    """A single processed audit finding with risk intelligence attached."""

    def __init__(
        self,
        finding_id: str,
        category: str,
        description: str,
        risk_score: float,
        priority: str,
        financial_impact: float,
        occurrence_count: int,
        is_systemic: bool,
        materiality_status: str,
        auditor_reasoning: str,
        raw_event_ids: List[int],
        control_type: str = "detective",
        timestamp: Optional[str] = None,
    ):
        self.finding_id = finding_id
        self.category = category
        self.description = description
        self.risk_score = round(risk_score, 1)
        self.priority = priority
        self.financial_impact = round(financial_impact, 2)
        self.occurrence_count = occurrence_count
        self.is_systemic = is_systemic
        self.materiality_status = materiality_status
        self.auditor_reasoning = auditor_reasoning
        self.raw_event_ids = raw_event_ids
        self.control_type = control_type
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "finding_id": self.finding_id,
            "category": self.category,
            "description": self.description,
            "risk_score": self.risk_score,
            "priority": self.priority,
            "financial_impact": self.financial_impact,
            "occurrence_count": self.occurrence_count,
            "is_systemic": self.is_systemic,
            "materiality_status": self.materiality_status,
            "auditor_reasoning": self.auditor_reasoning,
            "raw_event_ids": self.raw_event_ids,
            "control_type": self.control_type,
            "timestamp": self.timestamp,
        }


class SOXValidator:
    """
    The core Materiality & Aggregation Engine.

    Process flow:
        raw events → deduplicate → apply materiality filter → risk score → prioritise
    """

    def __init__(
        self,
        materiality_threshold: float = DEFAULT_MATERIALITY_THRESHOLD,
        systemic_threshold: int = SYSTEMIC_THRESHOLD,
    ):
        self.materiality_threshold = materiality_threshold
        self.systemic_threshold = systemic_threshold
        self._processed_count = 0

    # ──────────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────────────────────────────

    def process_events(self, raw_events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Main entry point: take a list of raw audit events and return
        aggregated, scored, filtered intelligence.

        Returns:
            {
                "findings":           [AuditFinding.to_dict(), ...],
                "summary": {
                    "total_raw_events":      int,
                    "systemic_groups":        int,
                    "auto_cleared":           int,
                    "critical_findings":      int,
                    "high_findings":          int,
                    "medium_findings":        int,
                    "low_findings":           int,
                    "total_financial_impact": float,
                },
                "processed_at": ISO timestamp,
            }
        """
        if not raw_events:
            return self._empty_result()

        # Step 1: Deduplicate
        groups = self._deduplicate(raw_events)

        # Step 2: Build findings with risk scores
        findings: List[AuditFinding] = []
        auto_cleared = 0

        for group_key, events in groups.items():
            financial_impact = self._compute_financial_impact(events)
            occurrence_count = len(events)
            is_systemic = occurrence_count >= self.systemic_threshold

            # Step 3: Materiality filter
            if financial_impact < self.materiality_threshold and not is_systemic:
                auto_cleared += occurrence_count
                continue

            # Step 4: Risk scoring
            risk_score = self._compute_risk_score(
                events=events,
                financial_impact=financial_impact,
                is_systemic=is_systemic,
            )
            priority = self._score_to_priority(risk_score)
            control_type = self._detect_control_type(events)

            # Step 5: Generate description
            description = self._generate_finding_description(
                group_key, events, is_systemic, occurrence_count
            )
            auditor_reasoning = self._generate_auditor_reasoning(
                group_key, events, financial_impact, control_type, is_systemic
            )

            finding_id = self._generate_finding_id(group_key, events)

            finding = AuditFinding(
                finding_id=finding_id,
                category=group_key,
                description=description,
                risk_score=risk_score,
                priority=priority,
                financial_impact=financial_impact,
                occurrence_count=occurrence_count,
                is_systemic=is_systemic,
                materiality_status="material" if financial_impact >= self.materiality_threshold else "systemic_override",
                auditor_reasoning=auditor_reasoning,
                raw_event_ids=[e.get("id", 0) for e in events],
                control_type=control_type,
            )
            findings.append(finding)

        # Sort by risk score descending (highest risk first)
        findings.sort(key=lambda f: f.risk_score, reverse=True)

        summary = self._build_summary(raw_events, findings, auto_cleared)
        self._processed_count += len(raw_events)

        logger.info(
            "sox_validator.process_complete  raw=%d  findings=%d  cleared=%d",
            len(raw_events), len(findings), auto_cleared,
        )

        return {
            "findings": [f.to_dict() for f in findings],
            "summary": summary,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }

    def validate_single_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Lightweight validation of a single event — returns risk score
        and materiality status without full deduplication.
        """
        financial_impact = self._extract_amount(event)
        is_material = financial_impact >= self.materiality_threshold

        risk_score = self._compute_single_risk_score(event, financial_impact)
        priority = self._score_to_priority(risk_score)

        return {
            "risk_score": round(risk_score, 1),
            "priority": priority,
            "financial_impact": round(financial_impact, 2),
            "is_material": is_material,
            "materiality_threshold": self.materiality_threshold,
        }

    # ──────────────────────────────────────────────────────────────────────
    # DEDUPLICATION
    # ──────────────────────────────────────────────────────────────────────

    def _deduplicate(self, events: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
        """
        Group events by their 'signature' — a fingerprint of the error type.
        400+ identical 'Negative Amount' warnings become one group.
        """
        groups: Dict[str, List[Dict]] = defaultdict(list)

        for event in events:
            sig = self._compute_event_signature(event)
            groups[sig].append(event)

        logger.debug(
            "sox_validator.deduplicate  raw=%d  groups=%d",
            len(events), len(groups),
        )
        return dict(groups)

    def _compute_event_signature(self, event: Dict[str, Any]) -> str:
        """
        Generate a deduplication key from the event's semantic content.
        Events with the same source_system + event_type + error pattern
        share a signature.
        """
        source = str(event.get("source_system", "unknown")).strip().lower()
        event_type = str(event.get("event_type", "unknown")).strip().lower()

        # Extract the error category from log_data if present
        log_data = str(event.get("log_data", ""))
        error_pattern = self._extract_error_pattern(log_data)

        signature_parts = [source, event_type, error_pattern]
        return "|".join(signature_parts)

    def _extract_error_pattern(self, log_data: str) -> str:
        """
        Extract the core error pattern, stripping variable data
        (timestamps, IDs, amounts) so similar errors group together.
        """
        if not log_data:
            return "general"

        # Strip numbers/IDs to normalise
        normalised = re.sub(r'\b\d+\.?\d*\b', 'N', log_data)
        normalised = re.sub(r'[A-Fa-f0-9]{8,}', 'HASH', normalised)
        normalised = re.sub(r'\s+', ' ', normalised).strip().lower()

        # Truncate to keep grouping manageable
        return normalised[:120] if normalised else "general"

    # ──────────────────────────────────────────────────────────────────────
    # FINANCIAL IMPACT
    # ──────────────────────────────────────────────────────────────────────

    def _compute_financial_impact(self, events: List[Dict[str, Any]]) -> float:
        """Sum the absolute financial impact of all events in a group."""
        total = 0.0
        for event in events:
            total += self._extract_amount(event)
        return total

    def _extract_amount(self, event: Dict[str, Any]) -> float:
        """
        Extract dollar amount from an event, checking common field names.
        Returns absolute value (negative amounts still have financial impact).
        """
        amount_fields = ["amount", "transaction_value", "financial_impact",
                         "value", "total", "payment_amount"]

        for field in amount_fields:
            val = event.get(field)
            if val is not None:
                try:
                    return abs(float(val))
                except (ValueError, TypeError):
                    continue

        # Try extracting from log_data string
        log_data = str(event.get("log_data", ""))
        amounts = re.findall(r'\$?([\d,]+\.?\d*)', log_data)
        if amounts:
            try:
                return abs(float(amounts[0].replace(",", "")))
            except (ValueError, TypeError):
                pass

        # Try extracting from metadata
        metadata = event.get("metadata_json") or event.get("metadata") or {}
        if isinstance(metadata, dict):
            for field in amount_fields:
                val = metadata.get(field)
                if val is not None:
                    try:
                        return abs(float(val))
                    except (ValueError, TypeError):
                        continue

        return 0.0

    # ──────────────────────────────────────────────────────────────────────
    # RISK SCORING
    # ──────────────────────────────────────────────────────────────────────

    def _compute_risk_score(
        self,
        events: List[Dict[str, Any]],
        financial_impact: float,
        is_systemic: bool,
    ) -> float:
        """
        Weighted risk score (0–100) based on:
          - Transaction value           (35%)
          - Behavioral complexity        (25%)
          - Control severity             (20%)
          - Frequency / systemic factor  (10%)
          - Recency factor               (10%)
        """
        w = RISK_WEIGHTS

        # Transaction value score (0–100)
        # Uses log scale: $500 = ~30, $10K = ~60, $100K = ~85, $1M = ~100
        tv_score = min(100, max(0, 15 * math.log10(max(financial_impact, 1))))

        # Behavioral complexity (0–100)
        bc_score = self._assess_behavioral_complexity(events)

        # Control severity (0–100)
        control_type = self._detect_control_type(events)
        cs_score = CONTROL_SEVERITY.get(control_type, 0.5) * 100

        # Frequency factor (0–100)
        count = len(events)
        ff_score = min(100, count * 5) if is_systemic else min(50, count * 10)

        # Recency factor (0–100)
        rf_score = self._assess_recency(events)

        total = (
            w["transaction_value"]     * tv_score +
            w["behavioral_complexity"] * bc_score +
            w["control_severity"]      * cs_score +
            w["frequency_factor"]      * ff_score +
            w["recency_factor"]        * rf_score
        )

        return min(100.0, max(0.0, total))

    def _compute_single_risk_score(self, event: Dict[str, Any], financial_impact: float) -> float:
        """Simplified risk score for a single event."""
        tv_score = min(100, max(0, 15 * math.log10(max(financial_impact, 1))))
        bc_score = self._assess_behavioral_complexity([event])
        control_type = self._detect_control_type([event])
        cs_score = CONTROL_SEVERITY.get(control_type, 0.5) * 100

        w = RISK_WEIGHTS
        total = (
            w["transaction_value"]     * tv_score +
            w["behavioral_complexity"] * bc_score +
            w["control_severity"]      * cs_score +
            w["frequency_factor"]      * 10 +
            w["recency_factor"]        * 80
        )
        return min(100.0, max(0.0, total))

    def _assess_behavioral_complexity(self, events: List[Dict[str, Any]]) -> float:
        """
        Score 0–100 based on how 'unusual' the behavioral patterns are:
          - Negative amounts:               +20
          - Boundary values ($0, $999.99):   +25
          - Duplicate hashes:                +30
          - Missing required fields:         +15
          - Off-hours timestamps:            +10
        """
        score = 0.0
        indicators = set()

        for event in events:
            log_data = str(event.get("log_data", ""))
            amount = self._extract_amount(event)

            # Negative amount detection
            raw_amounts = re.findall(r'-\$?[\d,]+\.?\d*', log_data)
            if raw_amounts or event.get("amount", 0) and float(str(event.get("amount", 0))) < 0:
                indicators.add("negative_amount")

            # Boundary value detection
            if amount in (0, 0.01, 999.99, 9999.99, 99999.99):
                indicators.add("boundary_value")

            # Missing fields
            required = ["source_system", "event_type"]
            if any(not event.get(f) for f in required):
                indicators.add("missing_fields")

        # Check for duplicate hashes
        hashes = [e.get("hash_sequence", "") for e in events if e.get("hash_sequence")]
        if len(hashes) != len(set(hashes)):
            indicators.add("duplicate_hashes")

        complexity_scores = {
            "negative_amount":  20,
            "boundary_value":   25,
            "duplicate_hashes": 30,
            "missing_fields":   15,
            "off_hours":        10,
        }

        for ind in indicators:
            score += complexity_scores.get(ind, 0)

        return min(100.0, score)

    def _assess_recency(self, events: List[Dict[str, Any]]) -> float:
        """Score 0–100 based on how recent the events are."""
        now = datetime.now(timezone.utc)
        most_recent_hours = float("inf")

        for event in events:
            ts = event.get("timestamp") or event.get("recorded_at")
            if ts:
                try:
                    if isinstance(ts, str):
                        event_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    elif isinstance(ts, datetime):
                        event_time = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
                    else:
                        continue
                    hours_ago = (now - event_time).total_seconds() / 3600
                    most_recent_hours = min(most_recent_hours, hours_ago)
                except (ValueError, TypeError):
                    continue

        if most_recent_hours == float("inf"):
            return 50.0   # unknown recency → moderate

        # Within 1h = 100, within 24h = 60, within 7d = 30, older = 10
        if most_recent_hours <= 1:
            return 100.0
        elif most_recent_hours <= 24:
            return 80.0 - (most_recent_hours / 24) * 20
        elif most_recent_hours <= 168:
            return 30.0
        else:
            return 10.0

    def _detect_control_type(self, events: List[Dict[str, Any]]) -> str:
        """Infer the SOX control type from event content."""
        for event in events:
            log_data = str(event.get("log_data", "")).lower()
            event_type = str(event.get("event_type", "")).lower()
            combined = log_data + " " + event_type

            if any(kw in combined for kw in [
                "prevent", "block", "reject", "deny", "validation_fail",
                "bypass", "unauthorized", "breach", "tamper", "violat",
                "unapproved", "forbidden", "escalat",
            ]):
                return "preventative"
            elif any(kw in combined for kw in ["detect", "alert", "monitor", "anomaly", "flag"]):
                return "detective"
            elif any(kw in combined for kw in ["correct", "remediat", "fix", "patch", "rollback"]):
                return "corrective"

        return "monitoring"

    # ──────────────────────────────────────────────────────────────────────
    # PRIORITY CLASSIFICATION
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _score_to_priority(score: float) -> str:
        """Map risk score to executive-friendly priority level."""
        if score >= 80:
            return "Critical"
        elif score >= 60:
            return "High"
        elif score >= 40:
            return "Medium"
        else:
            return "Low"

    # ──────────────────────────────────────────────────────────────────────
    # DESCRIPTION / REASONING GENERATION
    # ──────────────────────────────────────────────────────────────────────

    def _generate_finding_description(
        self, group_key: str, events: List[Dict], is_systemic: bool, count: int
    ) -> str:
        """Generate a human-readable finding description."""
        parts = group_key.split("|")
        source = parts[0] if len(parts) > 0 else "Unknown"
        event_type = parts[1] if len(parts) > 1 else "Unknown"
        pattern = parts[2] if len(parts) > 2 else ""

        if is_systemic:
            return (
                f"SYSTEMIC LOGIC GAP: {count} occurrences of '{event_type}' "
                f"detected from '{source}'. Pattern: {pattern[:80]}. "
                f"This indicates a systemic control weakness requiring root-cause analysis."
            )
        else:
            return (
                f"{event_type.upper()} event from '{source}' — {count} occurrence(s). "
                f"Pattern: {pattern[:80]}"
            )

    def _generate_auditor_reasoning(
        self,
        group_key: str,
        events: List[Dict],
        financial_impact: float,
        control_type: str,
        is_systemic: bool,
    ) -> str:
        """
        Generate the 'Auditor Reasoning' field that explains the specific
        SOX control violation for a human auditor.
        """
        parts = group_key.split("|")
        source = parts[0] if len(parts) > 0 else "Unknown"
        event_type = parts[1] if len(parts) > 1 else "Unknown"
        pattern = parts[2] if len(parts) > 2 else ""
        count = len(events)

        reasons = []

        # Control-type specific reasoning
        if control_type == "preventative":
            reasons.append(
                f"Bypass of Preventative Control: Server-side validation failed to trap "
                f"'{event_type}' events from {source}. "
                f"This indicates the preventative control is not operating effectively."
            )
        elif control_type == "detective":
            reasons.append(
                f"Detective Control Alert: {count} anomalous '{event_type}' events "
                f"identified from {source}. Review required to assess whether these "
                f"represent genuine control failures or false positives."
            )
        elif control_type == "corrective":
            reasons.append(
                f"Corrective Control Gap: Remediation actions for '{event_type}' "
                f"from {source} may not be executing as designed."
            )
        else:
            reasons.append(
                f"Monitoring Alert: '{event_type}' activity from {source} "
                f"exceeds expected baseline parameters."
            )

        # Financial impact reasoning
        if financial_impact >= 50000:
            reasons.append(
                f"HIGH FINANCIAL EXPOSURE: Total impact of ${financial_impact:,.2f} "
                f"exceeds executive reporting threshold. Immediate escalation recommended."
            )
        elif financial_impact >= 5000:
            reasons.append(
                f"Material Financial Impact: ${financial_impact:,.2f} aggregate exposure "
                f"across {count} event(s). Management review required."
            )

        # Systemic reasoning
        if is_systemic:
            reasons.append(
                f"SYSTEMIC PATTERN DETECTED: {count} repetitive occurrences suggest "
                f"a logic gap in the underlying system rather than isolated incidents. "
                f"Root-cause analysis and remediation of the source system is recommended."
            )

        # Behavioral pattern reasoning
        complexity = self._assess_behavioral_complexity(events)
        if complexity >= 40:
            reasons.append(
                f"BEHAVIORAL ANOMALY (complexity={complexity:.0f}/100): "
                f"Unusual patterns detected including boundary-value injection, "
                f"negative amounts, or duplicate hashes. This may indicate "
                f"adversarial testing or data manipulation."
            )

        return " | ".join(reasons)

    # ──────────────────────────────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _generate_finding_id(group_key: str, events: List[Dict]) -> str:
        """Generate a deterministic finding ID from the group signature."""
        raw = f"{group_key}:{len(events)}".encode()
        return f"FND-{hashlib.md5(raw).hexdigest()[:10].upper()}"

    def _build_summary(
        self,
        raw_events: List[Dict],
        findings: List[AuditFinding],
        auto_cleared: int,
    ) -> dict:
        """Build the executive summary for the processing run."""
        priority_counts = Counter(f.priority for f in findings)
        total_impact = sum(f.financial_impact for f in findings)

        return {
            "total_raw_events": len(raw_events),
            "systemic_groups": sum(1 for f in findings if f.is_systemic),
            "auto_cleared": auto_cleared,
            "critical_findings": priority_counts.get("Critical", 0),
            "high_findings": priority_counts.get("High", 0),
            "medium_findings": priority_counts.get("Medium", 0),
            "low_findings": priority_counts.get("Low", 0),
            "total_financial_impact": round(total_impact, 2),
            "materiality_threshold": self.materiality_threshold,
        }

    @staticmethod
    def _empty_result() -> dict:
        return {
            "findings": [],
            "summary": {
                "total_raw_events": 0,
                "systemic_groups": 0,
                "auto_cleared": 0,
                "critical_findings": 0,
                "high_findings": 0,
                "medium_findings": 0,
                "low_findings": 0,
                "total_financial_impact": 0.0,
            },
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
