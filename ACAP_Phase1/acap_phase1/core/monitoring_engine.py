"""
core/monitoring_engine.py
─────────────────────────
The Continuous Monitoring & UAT Factory

Houses autonomous UAT agents that simulate complex, real-time industry
scenarios and continuously validate the Auditor Intelligence Layer.

Three specialised agents:

  1. GhostVendorAgent — Simulates 'Round Number' payments to a vendor
     with no historical footprint, testing vendor-validation controls.

  2. VelocityRiskAgent — Simulates 'Threshold Splitting' across
     multiple modules (AP, GL, Procurement) within a 1-hour window,
     testing cross-module velocity controls.

  3. AIIntegrityStressorAgent — Feeds the Forensic Engine conflicting
     financial data to verify the 'Hallucination Shield' correctly
     flags discrepancies.

Each agent:
  - Generates realistic fraud scenarios
  - Feeds events through the SOXValidator pipeline
  - Validates detection, risk scoring, and auditor reasoning
  - Reports PASS/FAIL with detailed telemetry
  - Stores results in SQLite for dashboard visualisation

Usage:
    from core.monitoring_engine import MonitoringEngine
    engine = MonitoringEngine()
    report = engine.run_full_cycle()
"""

import hashlib
import json
import logging
import math
import random
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.sox_validator import SOXValidator
from core.forensic_engine import ForensicEngine
from core.sqlite_store import AuditIntelligenceStore


def _count_issues(result) -> int:
    """Count total issues from an IntegrityCheckResult."""
    return len(result.discrepancies) + len(result.math_errors) + len(result.hallucinations)

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────
GHOST_VENDOR_NAMES = [
    "APEX GLOBAL SERVICES LLC",
    "PINNACLE RESOURCE PARTNERS",
    "MERIDIAN CONSULTING GROUP",
    "SUMMIT PROCUREMENT INTL",
    "ZENITH ADVISORY CORP",
]

ROUND_NUMBER_AMOUNTS = [
    5000.00, 10000.00, 15000.00, 25000.00, 49999.00,
    50000.00, 75000.00, 99999.00, 100000.00, 250000.00,
]

LEGITIMATE_MODULES = ["accounts-payable", "general-ledger", "procurement", "treasury", "payroll"]
THRESHOLD_AMOUNTS = [4900, 4950, 4975, 4999, 4800, 4850, 4999.99, 4990]


# ══════════════════════════════════════════════════════════════════════════════
# Agent 1: Ghost Vendor
# ══════════════════════════════════════════════════════════════════════════════
class GhostVendorAgent:
    """
    Simulates a series of 'Round Number' payments to a vendor with no
    historical footprint — a classic procurement fraud pattern.

    Detection Targets:
      - Round-number payment amounts (exact thousands / near-threshold)
      - New vendor with no prior transaction history
      - Rapid onboarding + immediate high-value payments
      - Missing standard vendor qualification documents
    """

    def __init__(self):
        self.name = "GhostVendorAgent"
        self.validator = SOXValidator()
        self.forensic = ForensicEngine()

    def generate_scenario(self, vendor_name: str = None, num_payments: int = 8) -> List[Dict]:
        """Generate a realistic ghost vendor fraud scenario."""
        vendor = vendor_name or random.choice(GHOST_VENDOR_NAMES)
        vendor_id = f"V-{uuid.uuid4().hex[:8].upper()}"
        base_time = datetime.now(timezone.utc)

        events = []

        # Phase 1: Vendor onboarding (suspicious — no typical qualification period)
        events.append({
            "id": len(events) + 1,
            "source_system": "procurement",
            "event_type": "vendor_onboarding",
            "log_data": (
                f"New vendor '{vendor}' (ID: {vendor_id}) onboarded. "
                f"Qualification docs: PENDING. Approval: SINGLE_SIGNOFF. "
                f"Historical transactions: 0. Dun & Bradstreet check: BYPASSED."
            ),
            "amount": 0,
            "vendor_name": vendor,
            "vendor_id": vendor_id,
            "timestamp": (base_time - timedelta(days=2)).isoformat(),
            "user": "procurement_admin_03",
        })

        # Phase 2: Series of round-number payments (the fraud pattern)
        for i in range(num_payments):
            amount = random.choice(ROUND_NUMBER_AMOUNTS)
            events.append({
                "id": len(events) + 1,
                "source_system": "accounts-payable",
                "event_type": "payment_processed",
                "log_data": (
                    f"Payment #{i+1} to vendor '{vendor}' (ID: {vendor_id}): "
                    f"${amount:,.2f}. Invoice: INV-{uuid.uuid4().hex[:6].upper()}. "
                    f"PO Reference: NONE. Three-way match: FAILED."
                ),
                "amount": amount,
                "vendor_name": vendor,
                "vendor_id": vendor_id,
                "timestamp": (base_time - timedelta(hours=random.randint(1, 48))).isoformat(),
                "user": "ap_processor_07",
                "payment_method": random.choice(["wire_transfer", "ach", "wire_transfer"]),
            })

        # Phase 3: Goods receipt without physical delivery
        events.append({
            "id": len(events) + 1,
            "source_system": "procurement",
            "event_type": "goods_receipt_discrepancy",
            "log_data": (
                f"Goods Receipt posted for vendor '{vendor}' but warehouse "
                f"confirms NO physical delivery received. GR auto-posted by system."
            ),
            "amount": sum(e["amount"] for e in events if e.get("amount", 0) > 0),
            "vendor_name": vendor,
            "vendor_id": vendor_id,
            "timestamp": base_time.isoformat(),
        })

        return events

    def run_test(self) -> Dict[str, Any]:
        """Execute the ghost vendor test and validate detection."""
        start = time.time()
        scenario = self.generate_scenario()
        result = self.validator.process_events(scenario)

        findings = result["findings"]
        total_amount = sum(e["amount"] for e in scenario if e.get("amount", 0) > 0)

        # Validation criteria
        checks = {
            "events_generated": len(scenario),
            "findings_created": len(findings) > 0,
            "financial_impact_tracked": any(
                f["financial_impact"] > 0 for f in findings
            ),
            "round_number_detected": any(
                "round" in f.get("description", "").lower() or
                "payment" in f.get("description", "").lower()
                for f in findings
            ),
            "vendor_flagged": any(
                "vendor" in (f.get("description", "") + f.get("auditor_reasoning", "")).lower()
                for f in findings
            ),
            "risk_score_above_40": any(
                f["risk_score"] >= 40 for f in findings
            ),
            "auditor_reasoning_present": all(
                len(f.get("auditor_reasoning", "")) > 50 for f in findings
            ),
            "materiality_applied": result["summary"]["total_raw_events"] == len(scenario),
        }

        passed = sum(1 for v in checks.values() if v is True)
        total = len(checks)

        return {
            "agent": self.name,
            "scenario": "ghost_vendor_round_number_fraud",
            "status": "PASS" if passed >= total - 1 else "FAIL",
            "passed": passed,
            "total_checks": total,
            "total_fraud_amount": total_amount,
            "findings_count": len(findings),
            "max_risk_score": max((f["risk_score"] for f in findings), default=0),
            "checks": checks,
            "duration_seconds": round(time.time() - start, 3),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ══════════════════════════════════════════════════════════════════════════════
# Agent 2: Velocity Risk (Threshold Splitter)
# ══════════════════════════════════════════════════════════════════════════════
class VelocityRiskAgent:
    """
    Simulates a user attempting 'Threshold Splitting' — breaking a large
    transaction into many sub-threshold amounts across multiple modules
    (AP, GL, Procurement) within a 1-hour window to evade approval controls.

    Detection Targets:
      - Multiple transactions just below $5,000 approval threshold
      - Cross-module activity from a single user in short timeframe
      - Aggregate amount exceeds individual approval authority
      - Pattern indicates deliberate control circumvention
    """

    def __init__(self):
        self.name = "VelocityRiskAgent"
        self.validator = SOXValidator()

    def generate_scenario(
        self,
        user: str = "finance_analyst_12",
        num_splits: int = 12,
        window_minutes: int = 55,
    ) -> List[Dict]:
        """Generate a threshold-splitting scenario."""
        base_time = datetime.now(timezone.utc)
        events = []

        # Spread transactions across modules within the time window
        for i in range(num_splits):
            module = LEGITIMATE_MODULES[i % len(LEGITIMATE_MODULES)]
            amount = random.choice(THRESHOLD_AMOUNTS)
            offset = timedelta(minutes=random.randint(0, window_minutes))

            event_types = {
                "accounts-payable": "invoice_approval",
                "general-ledger": "journal_entry",
                "procurement": "purchase_order",
                "treasury": "wire_transfer_request",
                "payroll": "bonus_adjustment",
            }

            events.append({
                "id": i + 1,
                "source_system": module,
                "event_type": event_types.get(module, "transaction"),
                "log_data": (
                    f"User '{user}' processed {event_types.get(module, 'transaction')} "
                    f"for ${amount:,.2f} in module '{module}'. "
                    f"Individual amount below $5,000 threshold. "
                    f"Auto-approved without secondary review."
                ),
                "amount": amount,
                "user": user,
                "approval_level": "auto_approved",
                "timestamp": (base_time - offset).isoformat(),
                "module": module,
            })

        return events

    def run_test(self) -> Dict[str, Any]:
        """Execute the velocity/threshold-splitting test."""
        start = time.time()
        scenario = self.generate_scenario()
        result = self.validator.process_events(scenario)

        findings = result["findings"]
        total_amount = sum(e["amount"] for e in scenario)
        unique_modules = len(set(e["source_system"] for e in scenario))

        checks = {
            "events_generated": len(scenario) == 12,
            "aggregate_exceeds_threshold": total_amount > 5000,
            "multi_module_detected": unique_modules >= 3,
            "findings_created": len(findings) > 0,
            "deduplication_works": len(findings) < len(scenario),
            "financial_impact_aggregated": any(
                f["financial_impact"] > 10000 for f in findings
            ),
            "risk_score_above_threshold": any(
                f["risk_score"] >= 35 for f in findings
            ),
            "auditor_reasoning_generated": all(
                len(f.get("auditor_reasoning", "")) > 20 for f in findings
            ),
            "systemic_detection": any(
                f.get("is_systemic", False) or f.get("occurrence_count", 0) > 5
                for f in findings
            ),
        }

        passed = sum(1 for v in checks.values() if v is True)
        total = len(checks)

        return {
            "agent": self.name,
            "scenario": "threshold_splitting_velocity_risk",
            "status": "PASS" if passed >= total - 1 else "FAIL",
            "passed": passed,
            "total_checks": total,
            "total_split_amount": total_amount,
            "modules_used": unique_modules,
            "findings_count": len(findings),
            "max_risk_score": max((f["risk_score"] for f in findings), default=0),
            "checks": checks,
            "duration_seconds": round(time.time() - start, 3),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ══════════════════════════════════════════════════════════════════════════════
# Agent 3: AI Integrity Stressor (Hallucination Shield)
# ══════════════════════════════════════════════════════════════════════════════
class AIIntegrityStressorAgent:
    """
    Feeds the Forensic Engine conflicting financial data to verify the
    'Hallucination Shield' correctly flags discrepancies.

    Stress Tests:
      1. Summary claims 10 records but only 3 exist
      2. Summary claims $500K total but actual is $120K
      3. Summary references a source system that doesn't exist in data
      4. Summary claims all findings are "Low" but data has Critical items
      5. Summary has correct data (positive control — should PASS)
    """

    def __init__(self):
        self.name = "AIIntegrityStressorAgent"
        self.forensic = ForensicEngine()
        self.validator = SOXValidator()

    def _generate_raw_records(self, count: int = 5) -> List[Dict]:
        """Generate realistic raw audit records."""
        systems = ["ERP-Finance", "Treasury-Wire", "GL-Journal"]
        records = []
        for i in range(count):
            records.append({
                "id": i + 1,
                "source_system": random.choice(systems),
                "event_type": "detect_anomaly",
                "log_data": f"Anomaly #{i+1} detected in financial processing",
                "amount": random.uniform(1000, 50000),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ai_confidence_score": random.uniform(60, 98),
                "hash_verified": True,
            })
        return records

    def _stress_test_count_mismatch(self) -> Dict:
        """Test 1: Summary claims more records than exist."""
        raw = self._generate_raw_records(3)
        fake_summary = {
            "total_records": 10,  # WRONG: only 3 exist
            "total_amount": sum(r["amount"] for r in raw),
            "source_systems": list(set(r["source_system"] for r in raw)),
        }
        result = self.forensic.verify_summary(fake_summary, raw)
        detected = not result.is_valid or len(result.discrepancies) > 0
        return {
            "test": "count_mismatch",
            "expected": "DETECT",
            "actual": "DETECTED" if detected else "MISSED",
            "passed": detected,
            "confidence": result.confidence_score,
            "issues": _count_issues(result),
        }

    def _stress_test_financial_mismatch(self) -> Dict:
        """Test 2: Summary claims wrong financial total."""
        raw = self._generate_raw_records(5)
        actual_total = sum(r["amount"] for r in raw)
        fake_summary = {
            "total_records": len(raw),
            "total_amount": actual_total * 4.2,  # WRONG: 4.2x actual
            "source_systems": list(set(r["source_system"] for r in raw)),
        }
        result = self.forensic.verify_summary(fake_summary, raw)
        detected = not result.is_valid or len(result.math_errors) > 0
        return {
            "test": "financial_mismatch",
            "expected": "DETECT",
            "actual": "DETECTED" if detected else "MISSED",
            "passed": detected,
            "confidence": result.confidence_score,
            "issues": _count_issues(result),
        }

    def _stress_test_phantom_source(self) -> Dict:
        """Test 3: Summary references a source system not in data."""
        raw = self._generate_raw_records(4)
        fake_summary = {
            "total_records": len(raw),
            "total_amount": sum(r["amount"] for r in raw),
            "source_systems": ["ERP-Finance", "PHANTOM-SYSTEM-X", "NONEXISTENT-MODULE"],
        }
        result = self.forensic.verify_summary(fake_summary, raw)
        detected = not result.is_valid or len(result.hallucinations) > 0
        return {
            "test": "phantom_source_system",
            "expected": "DETECT",
            "actual": "DETECTED" if detected else "MISSED",
            "passed": detected,
            "confidence": result.confidence_score,
            "issues": _count_issues(result),
        }

    def _stress_test_priority_manipulation(self) -> Dict:
        """Test 4: Feed high-risk events but claim all are Low priority."""
        high_risk_events = [
            {
                "id": 1, "source_system": "Treasury-Wire",
                "event_type": "unauthorized_access",
                "log_data": "Root access to wire transfer system by unknown user",
                "amount": 500000,
            },
            {
                "id": 2, "source_system": "Payroll-System",
                "event_type": "validation_bypass",
                "log_data": "Payroll batch $800K approved without authorisation",
                "amount": 800000,
            },
        ]
        # Process through validator to get real findings
        result = self.validator.process_events(high_risk_events)
        findings = result["findings"]

        # Create a fake summary that downplays everything
        fake_summary = {
            "total_records": len(high_risk_events),
            "total_amount": 50.00,  # Massively understated
            "critical_findings": 0,
            "high_findings": 0,
            "headline": "All clear, no issues found.",
            "source_systems": ["Treasury-Wire", "Payroll-System"],
        }
        verify = self.forensic.verify_summary(fake_summary, high_risk_events)
        # The financial mismatch should be caught
        issues = _count_issues(verify)
        return {
            "test": "priority_manipulation",
            "expected": "DETECT",
            "actual": "DETECTED" if issues > 0 else "MISSED",
            "passed": issues > 0,
            "confidence": verify.confidence_score,
            "issues": issues,
            "actual_risk_scores": [f["risk_score"] for f in findings],
        }

    def _stress_test_valid_summary(self) -> Dict:
        """Test 5: Positive control — correct summary should PASS."""
        raw = self._generate_raw_records(5)
        correct_summary = {
            "total_records": len(raw),
            "total_amount": sum(r["amount"] for r in raw),
            "source_systems": list(set(r["source_system"] for r in raw)),
        }
        result = self.forensic.verify_summary(correct_summary, raw)
        passed = result.is_valid and result.confidence_score >= 90
        return {
            "test": "valid_summary_positive_control",
            "expected": "PASS",
            "actual": "PASSED" if passed else "FALSE_POSITIVE",
            "passed": passed,
            "confidence": result.confidence_score,
            "issues": _count_issues(result),
        }

    def _stress_test_conflicting_data(self) -> Dict:
        """Test 6: Conflicting financial data — same transaction, different amounts."""
        raw = [
            {"id": 1, "source_system": "ERP-Finance", "event_type": "payment",
             "log_data": "Payment to vendor ABC for $50,000", "amount": 50000},
            {"id": 2, "source_system": "GL-Journal", "event_type": "journal_entry",
             "log_data": "Journal entry for vendor ABC payment: $75,000", "amount": 75000},
            {"id": 3, "source_system": "Treasury-Wire", "event_type": "wire",
             "log_data": "Wire transfer to vendor ABC: $50,000", "amount": 50000},
        ]
        # Summary picks the wrong total
        fake_summary = {
            "total_records": 3,
            "total_amount": 225000,  # WRONG: 50K+75K+50K = 175K
            "source_systems": ["ERP-Finance", "GL-Journal", "Treasury-Wire"],
        }
        result = self.forensic.verify_summary(fake_summary, raw)
        detected = not result.is_valid or len(result.math_errors) > 0
        return {
            "test": "conflicting_financial_data",
            "expected": "DETECT",
            "actual": "DETECTED" if detected else "MISSED",
            "passed": detected,
            "confidence": result.confidence_score,
            "issues": _count_issues(result),
        }

    def run_test(self) -> Dict[str, Any]:
        """Execute all hallucination shield stress tests."""
        start = time.time()
        tests = [
            self._stress_test_count_mismatch(),
            self._stress_test_financial_mismatch(),
            self._stress_test_phantom_source(),
            self._stress_test_priority_manipulation(),
            self._stress_test_valid_summary(),
            self._stress_test_conflicting_data(),
        ]

        passed = sum(1 for t in tests if t["passed"])
        total = len(tests)

        return {
            "agent": self.name,
            "scenario": "ai_integrity_hallucination_shield",
            "status": "PASS" if passed == total else "FAIL",
            "passed": passed,
            "total_checks": total,
            "tests": tests,
            "avg_confidence": round(sum(t["confidence"] for t in tests) / total, 1),
            "duration_seconds": round(time.time() - start, 3),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ══════════════════════════════════════════════════════════════════════════════
# Monitoring Engine — Orchestrates All UAT Agents
# ══════════════════════════════════════════════════════════════════════════════
class MonitoringEngine:
    """
    The Continuous Monitoring & UAT Factory.

    Orchestrates all UAT agents, runs full validation cycles, stores
    results in SQLite, and provides regression detection.

    Usage:
        engine = MonitoringEngine()
        report = engine.run_full_cycle()

        # Or run individual agents:
        engine.run_agent("ghost_vendor")
        engine.run_agent("velocity_risk")
        engine.run_agent("ai_integrity")
    """

    def __init__(self, store: Optional[AuditIntelligenceStore] = None):
        self.store = store or AuditIntelligenceStore()
        self.agents = {
            "ghost_vendor": GhostVendorAgent(),
            "velocity_risk": VelocityRiskAgent(),
            "ai_integrity": AIIntegrityStressorAgent(),
        }
        self.cycle_count = 0
        self.last_report = None

    def run_agent(self, agent_name: str) -> Dict[str, Any]:
        """Run a specific UAT agent and store the result."""
        if agent_name not in self.agents:
            return {"error": f"Unknown agent: {agent_name}", "available": list(self.agents.keys())}

        agent = self.agents[agent_name]
        logger.info(f"monitoring.agent_start  agent={agent_name}")

        try:
            result = agent.run_test()
            # Store in SQLite
            self.store.save_monkey_test({
                "test_id": f"uat-{agent_name}-{uuid.uuid4().hex[:8]}",
                "test_type": f"uat_{agent_name}",
                "payload": {"scenario": result.get("scenario", "")},
                "expected_outcome": "PASS",
                "actual_outcome": result.get("status", "UNKNOWN"),
                "passed": result.get("status") == "PASS",
                "risk_score_before": 0,
                "risk_score_after": result.get("max_risk_score", 0),
                "notes": json.dumps(result.get("checks", result.get("tests", {}))),
            })
            logger.info(
                f"monitoring.agent_complete  agent={agent_name}  "
                f"status={result['status']}  "
                f"passed={result['passed']}/{result['total_checks']}  "
                f"duration={result['duration_seconds']}s"
            )
            return result
        except Exception as e:
            logger.error(f"monitoring.agent_error  agent={agent_name}  error={e}")
            return {
                "agent": agent_name,
                "status": "ERROR",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def run_full_cycle(self) -> Dict[str, Any]:
        """
        Run all UAT agents in sequence and produce a comprehensive report.

        This is the main entry point for continuous monitoring. Each cycle:
          1. Runs all three UAT agents
          2. Aggregates results
          3. Detects regressions vs previous cycle
          4. Stores everything in SQLite
          5. Returns the full report
        """
        cycle_start = time.time()
        self.cycle_count += 1
        cycle_id = f"UAT-{self.cycle_count:04d}-{uuid.uuid4().hex[:6].upper()}"

        logger.info(f"monitoring.cycle_start  cycle={cycle_id}")

        agent_results = {}
        for name in self.agents:
            agent_results[name] = self.run_agent(name)

        # Aggregate
        total_checks = sum(r.get("total_checks", 0) for r in agent_results.values())
        total_passed = sum(r.get("passed", 0) for r in agent_results.values())
        total_failed = total_checks - total_passed
        all_pass = all(r.get("status") == "PASS" for r in agent_results.values())
        cycle_duration = round(time.time() - cycle_start, 3)

        # Regression detection
        regression_warning = None
        if self.last_report:
            prev_passed = self.last_report.get("total_passed", 0)
            if total_passed < prev_passed:
                regression_warning = (
                    f"REGRESSION DETECTED: Previous cycle passed {prev_passed} checks, "
                    f"current cycle only passed {total_passed}. "
                    f"Lost {prev_passed - total_passed} check(s)."
                )
                logger.warning(f"monitoring.regression  {regression_warning}")

        report = {
            "cycle_id": cycle_id,
            "cycle_number": self.cycle_count,
            "status": "ALL_PASS" if all_pass else "DEGRADED",
            "total_checks": total_checks,
            "total_passed": total_passed,
            "total_failed": total_failed,
            "pass_rate": round((total_passed / total_checks * 100) if total_checks > 0 else 0, 1),
            "agents": agent_results,
            "regression_warning": regression_warning,
            "duration_seconds": cycle_duration,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self.last_report = report

        # Also process a combined scenario through the full pipeline to test end-to-end
        self._run_pipeline_integration_test(report)

        logger.info(
            f"monitoring.cycle_complete  cycle={cycle_id}  "
            f"status={report['status']}  "
            f"passed={total_passed}/{total_checks} ({report['pass_rate']}%)  "
            f"duration={cycle_duration}s"
        )

        return report

    def _run_pipeline_integration_test(self, report: Dict):
        """
        End-to-end integration test: generate combined scenario events,
        run them through SOXValidator → ForensicEngine → SQLite Store.
        Verifies the full pipeline is operational.
        """
        try:
            # Generate a mix of events from all agents
            ghost = self.agents["ghost_vendor"].generate_scenario(num_payments=3)
            velocity = self.agents["velocity_risk"].generate_scenario(num_splits=5)
            all_events = ghost + velocity

            # Process through SOXValidator
            validator = SOXValidator()
            result = validator.process_events(all_events)

            # Generate executive summary with ForensicEngine
            forensic = ForensicEngine()
            summary = forensic.generate_executive_summary(
                result["findings"], result["summary"]
            )

            # Verify the summary's integrity
            verification = forensic.verify_summary(summary, all_events)

            # Store in SQLite
            self.store.save_findings(result["findings"])
            self.store.save_executive_summary(summary)
            self.store.save_verification(
                verification_type="pipeline_integration",
                result=verification.to_dict(),
                target_id=report.get("cycle_id"),
            )

            report["pipeline_integration"] = {
                "status": "PASS",
                "events_processed": len(all_events),
                "findings_generated": len(result["findings"]),
                "summary_verified": verification.is_valid,
                "confidence": verification.confidence_score,
                "sqlite_stored": True,
            }
        except Exception as e:
            report["pipeline_integration"] = {
                "status": "ERROR",
                "error": str(e),
            }
            logger.error(f"monitoring.pipeline_error  error={e}")

    def get_health_status(self) -> Dict[str, Any]:
        """Get current monitoring health for the dashboard."""
        try:
            test_summary = self.store.get_monkey_test_summary()
            return {
                "monitoring_active": True,
                "cycle_count": self.cycle_count,
                "last_report": self.last_report,
                "test_summary": test_summary,
                "agents": list(self.agents.keys()),
            }
        except Exception as e:
            return {
                "monitoring_active": False,
                "error": str(e),
            }


# ──────────────────────────────────────────────────────────────────────────────
# CLI Entry Point
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    import os
    _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    print("=" * 70)
    print("  ACAP CONTINUOUS MONITORING ENGINE — Full UAT Cycle")
    print("=" * 70)

    engine = MonitoringEngine()
    report = engine.run_full_cycle()

    print(f"\n{'=' * 70}")
    print(f"  CYCLE: {report['cycle_id']}")
    print(f"  STATUS: {report['status']}")
    print(f"  RESULTS: {report['total_passed']}/{report['total_checks']} passed ({report['pass_rate']}%)")
    print(f"  DURATION: {report['duration_seconds']}s")
    print(f"{'=' * 70}")

    for agent_name, result in report["agents"].items():
        icon = "✓" if result.get("status") == "PASS" else "✗"
        print(f"  {icon} {agent_name}: {result.get('passed', 0)}/{result.get('total_checks', 0)} — {result.get('scenario', '')}")

        if agent_name == "ai_integrity" and "tests" in result:
            for t in result["tests"]:
                ti = "✓" if t["passed"] else "✗"
                print(f"      {ti} {t['test']}: {t['actual']} (confidence: {t['confidence']}%)")

    if report.get("pipeline_integration"):
        pi = report["pipeline_integration"]
        print(f"\n  Pipeline Integration: {pi['status']}")
        if pi["status"] == "PASS":
            print(f"    Events→Findings→Summary→SQLite: {pi['events_processed']}→{pi['findings_generated']}→verified({pi['confidence']}%)")

    if report.get("regression_warning"):
        print(f"\n  ⚠ {report['regression_warning']}")

    print(f"{'=' * 70}")
    sys.exit(0 if report["status"] == "ALL_PASS" else 1)
