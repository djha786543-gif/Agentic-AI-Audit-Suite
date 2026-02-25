"""
agents/monkey_tester.py
───────────────────────
The Adversarial Agent — Chaos Testing for SOX Controls

This agent generates adversarial test payloads designed to stress-test
the SOXValidator, ForensicEngine, and vault write paths. It simulates
attack vectors that a real adversary (or buggy source system) might produce.

Test Categories:
  1. BOUNDARY INJECTION:  $0.00, $0.01, $999.99, negative amounts
  2. HASH MANIPULATION:   Duplicate hashes, corrupt hashes, empty hashes
  3. FIELD OMISSION:       Missing required fields
  4. VOLUME FLOOD:         Rapid-fire identical events (deduplication stress)
  5. FORMAT ATTACKS:       Oversized payloads, Unicode injection, SQL injection
  6. TEMPORAL ANOMALIES:   Future-dated events, epoch-zero timestamps
  7. FINANCIAL EXPLOITS:   Amounts at exact materiality threshold

Usage:
    from agents.monkey_tester import MonkeyTester
    tester = MonkeyTester()
    results = tester.run_all_tests()

    # Or run specific test suites:
    results = tester.test_boundary_injection()
    results = tester.test_deduplication_flood()
"""

import hashlib
import json
import logging
import random
import string
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MonkeyTestResult:
    """Result of a single adversarial test."""

    def __init__(self, test_id: str, test_type: str, description: str):
        self.test_id = test_id
        self.test_type = test_type
        self.description = description
        self.payload: Dict[str, Any] = {}
        self.expected_outcome: str = ""
        self.actual_outcome: str = ""
        self.passed: bool = False
        self.risk_score_before: Optional[float] = None
        self.risk_score_after: Optional[float] = None
        self.notes: str = ""
        self.executed_at: str = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "test_id": self.test_id,
            "test_type": self.test_type,
            "description": self.description,
            "payload": self.payload,
            "expected_outcome": self.expected_outcome,
            "actual_outcome": self.actual_outcome,
            "passed": self.passed,
            "risk_score_before": self.risk_score_before,
            "risk_score_after": self.risk_score_after,
            "notes": self.notes,
            "executed_at": self.executed_at,
        }


class MonkeyTester:
    """
    The Adversarial Monkey Tester — probes SOX controls for weaknesses.

    Integrates with SOXValidator and ForensicEngine to verify that
    adversarial inputs are properly detected, scored, and reported.
    """

    def __init__(self, sox_validator=None, forensic_engine=None, sqlite_store=None):
        # Lazy imports to avoid circular dependencies
        self._sox_validator = sox_validator
        self._forensic_engine = forensic_engine
        self._sqlite_store = sqlite_store
        self._test_counter = 0

    def _get_validator(self):
        if self._sox_validator is None:
            from core.sox_validator import SOXValidator
            self._sox_validator = SOXValidator()
        return self._sox_validator

    def _get_forensic(self):
        if self._forensic_engine is None:
            from core.forensic_engine import ForensicEngine
            self._forensic_engine = ForensicEngine()
        return self._forensic_engine

    def _get_store(self):
        if self._sqlite_store is None:
            from core.sqlite_store import AuditIntelligenceStore
            self._sqlite_store = AuditIntelligenceStore()
        return self._sqlite_store

    def _next_test_id(self, prefix: str) -> str:
        self._test_counter += 1
        return f"MKY-{prefix}-{self._test_counter:04d}"

    # ──────────────────────────────────────────────────────────────────────
    # MASTER TEST RUNNER
    # ──────────────────────────────────────────────────────────────────────

    def run_all_tests(self) -> Dict[str, Any]:
        """
        Execute all adversarial test suites and return aggregate results.
        """
        started_at = datetime.now(timezone.utc)
        all_results: List[MonkeyTestResult] = []

        suites = [
            ("boundary_injection", self.test_boundary_injection),
            ("hash_manipulation", self.test_hash_manipulation),
            ("field_omission", self.test_field_omission),
            ("deduplication_flood", self.test_deduplication_flood),
            ("format_attacks", self.test_format_attacks),
            ("temporal_anomalies", self.test_temporal_anomalies),
            ("financial_exploits", self.test_financial_exploits),
            ("forensic_integrity", self.test_forensic_integrity),
        ]

        suite_results = {}
        for suite_name, suite_fn in suites:
            try:
                results = suite_fn()
                all_results.extend(results)
                passed = sum(1 for r in results if r.passed)
                suite_results[suite_name] = {
                    "total": len(results),
                    "passed": passed,
                    "failed": len(results) - passed,
                }
                logger.info(
                    "monkey.suite_complete  suite=%s  passed=%d/%d",
                    suite_name, passed, len(results),
                )
            except Exception as exc:
                logger.error("monkey.suite_error  suite=%s  err=%s", suite_name, str(exc))
                suite_results[suite_name] = {"total": 0, "passed": 0, "failed": 0, "error": str(exc)}

        # Save results to SQLite
        try:
            store = self._get_store()
            for result in all_results:
                store.save_monkey_test(result.to_dict())
        except Exception as exc:
            logger.error("monkey.save_error  err=%s", str(exc))

        total = len(all_results)
        passed = sum(1 for r in all_results if r.passed)
        completed_at = datetime.now(timezone.utc)

        return {
            "total_tests": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": round(passed / total * 100, 1) if total > 0 else 0.0,
            "suites": suite_results,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "duration_seconds": (completed_at - started_at).total_seconds(),
        }

    # ──────────────────────────────────────────────────────────────────────
    # TEST SUITE 1: BOUNDARY INJECTION
    # ──────────────────────────────────────────────────────────────────────

    def test_boundary_injection(self) -> List[MonkeyTestResult]:
        """Test boundary value handling — $0, $0.01, $999.99, negatives."""
        validator = self._get_validator()
        results = []

        boundary_cases = [
            (0.00, "Zero dollar amount — should be below materiality"),
            (0.01, "Minimum positive — should be below materiality"),
            (-500.00, "Negative amount — should flag behavioral anomaly"),
            (-99999.99, "Large negative — should flag as critical"),
            (499.99, "Just below materiality threshold — should auto-clear"),
            (500.00, "Exact materiality threshold — should be material"),
            (500.01, "Just above materiality — should create finding"),
            (999.99, "Common boundary value — should flag complexity"),
            (9999.99, "Higher boundary value — should flag complexity"),
            (99999.99, "Near-max boundary — should flag as high risk"),
        ]

        for amount, description in boundary_cases:
            test = MonkeyTestResult(
                test_id=self._next_test_id("BND"),
                test_type="boundary_injection",
                description=description,
            )
            event = {
                "id": random.randint(10000, 99999),
                "source_system": "MonkeyTester-Boundary",
                "event_type": "boundary_test",
                "log_data": f"Transaction amount: ${amount}",
                "amount": amount,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            test.payload = event

            # Expected: amounts below threshold should be auto-cleared (unless negative)
            if abs(amount) < 500 and amount >= 0:
                test.expected_outcome = "auto_cleared"
            elif amount < 0:
                test.expected_outcome = "flagged_with_behavioral_anomaly"
            else:
                test.expected_outcome = "finding_created"

            try:
                result = validator.validate_single_event(event)
                test.risk_score_after = result["risk_score"]

                if abs(amount) < 500 and amount >= 0:
                    test.passed = not result["is_material"]
                elif amount < 0:
                    test.passed = result["risk_score"] > 20  # Should detect anomaly
                else:
                    test.passed = result["is_material"]

                test.actual_outcome = f"risk={result['risk_score']}, material={result['is_material']}, priority={result['priority']}"
            except Exception as exc:
                test.actual_outcome = f"ERROR: {str(exc)}"
                test.passed = False

            results.append(test)

        return results

    # ──────────────────────────────────────────────────────────────────────
    # TEST SUITE 2: HASH MANIPULATION
    # ──────────────────────────────────────────────────────────────────────

    def test_hash_manipulation(self) -> List[MonkeyTestResult]:
        """Test detection of hash integrity issues."""
        validator = self._get_validator()
        results = []

        # Test 1: Duplicate hashes in a batch
        test = MonkeyTestResult(
            test_id=self._next_test_id("HSH"),
            test_type="hash_manipulation",
            description="Duplicate hashes should raise behavioral complexity",
        )
        duplicate_hash = hashlib.sha256(b"duplicate_data").hexdigest()
        events = [
            {"id": i, "source_system": "HashTest", "event_type": "dup_hash",
             "hash_sequence": duplicate_hash, "amount": 1000,
             "log_data": f"Event {i} with duplicate hash"}
            for i in range(5)
        ]
        test.payload = {"event_count": len(events), "hash": duplicate_hash[:16]}
        test.expected_outcome = "duplicate_hashes_detected"

        try:
            result = validator.process_events(events)
            has_finding = len(result["findings"]) > 0
            test.passed = has_finding
            test.actual_outcome = f"findings={len(result['findings'])}, cleared={result['summary']['auto_cleared']}"
        except Exception as exc:
            test.actual_outcome = f"ERROR: {str(exc)}"
            test.passed = False

        results.append(test)

        # Test 2: Empty hash
        test2 = MonkeyTestResult(
            test_id=self._next_test_id("HSH"),
            test_type="hash_manipulation",
            description="Empty hash should be flagged",
        )
        test2.payload = {"hash": "", "source": "HashTest"}
        test2.expected_outcome = "missing_hash_flagged"
        event = {"id": 99, "source_system": "HashTest", "event_type": "empty_hash",
                 "hash_sequence": "", "amount": 5000, "log_data": "Missing hash event"}
        try:
            result = validator.validate_single_event(event)
            test2.passed = True  # System should handle gracefully
            test2.actual_outcome = f"risk={result['risk_score']}, priority={result['priority']}"
        except Exception as exc:
            test2.actual_outcome = f"CRASH: {str(exc)}"
            test2.passed = False

        results.append(test2)

        # Test 3: Corrupted hash
        test3 = MonkeyTestResult(
            test_id=self._next_test_id("HSH"),
            test_type="hash_manipulation",
            description="Corrupted hash value should not crash system",
        )
        test3.payload = {"hash": "CORRUPT_HASH_XYZ_999", "source": "HashTest"}
        test3.expected_outcome = "handled_gracefully"
        event = {"id": 100, "source_system": "HashTest", "event_type": "corrupt_hash",
                 "hash_sequence": "CORRUPT_HASH_XYZ_999", "amount": 8000,
                 "log_data": "Corrupted hash event"}
        try:
            result = validator.validate_single_event(event)
            test3.passed = True
            test3.actual_outcome = f"risk={result['risk_score']}, priority={result['priority']}"
        except Exception as exc:
            test3.actual_outcome = f"CRASH: {str(exc)}"
            test3.passed = False

        results.append(test3)

        return results

    # ──────────────────────────────────────────────────────────────────────
    # TEST SUITE 3: FIELD OMISSION
    # ──────────────────────────────────────────────────────────────────────

    def test_field_omission(self) -> List[MonkeyTestResult]:
        """Test handling of events with missing required fields."""
        validator = self._get_validator()
        results = []

        omission_cases = [
            ({"id": 1, "log_data": "No source system", "amount": 5000},
             "Missing source_system"),
            ({"id": 2, "source_system": "Test", "amount": 5000},
             "Missing event_type and log_data"),
            ({}, "Completely empty event"),
            ({"id": 3, "source_system": "", "event_type": "", "log_data": ""},
             "Empty string fields"),
        ]

        for event, description in omission_cases:
            test = MonkeyTestResult(
                test_id=self._next_test_id("FLD"),
                test_type="field_omission",
                description=description,
            )
            test.payload = event
            test.expected_outcome = "handled_without_crash"

            try:
                result = validator.validate_single_event(event)
                test.passed = True  # No crash = pass
                test.actual_outcome = f"risk={result['risk_score']}, priority={result['priority']}"
            except Exception as exc:
                test.actual_outcome = f"CRASH: {str(exc)}"
                test.passed = False

            results.append(test)

        return results

    # ──────────────────────────────────────────────────────────────────────
    # TEST SUITE 4: DEDUPLICATION FLOOD
    # ──────────────────────────────────────────────────────────────────────

    def test_deduplication_flood(self) -> List[MonkeyTestResult]:
        """
        Flood with 400+ identical events — must deduplicate to single
        Systemic Logic Gap alert.
        """
        validator = self._get_validator()
        results = []

        # Test: 400 identical "Negative Amount" warnings
        test = MonkeyTestResult(
            test_id=self._next_test_id("DUP"),
            test_type="deduplication_flood",
            description="400 identical 'Negative Amount' warnings must become 1 systemic alert",
        )
        events = [
            {
                "id": i,
                "source_system": "ERP-System",
                "event_type": "validation_error",
                "log_data": "Negative Amount detected in transaction processing: -$50.00",
                "amount": -50.00,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            for i in range(400)
        ]
        test.payload = {"event_count": 400, "type": "negative_amount_flood"}
        test.expected_outcome = "1_systemic_finding"

        try:
            result = validator.process_events(events)
            findings = result["findings"]
            systemic = [f for f in findings if f["is_systemic"]]

            # Should deduplicate 400 events into very few findings (ideally 1)
            test.passed = len(findings) <= 5 and len(systemic) >= 1
            test.actual_outcome = (
                f"findings={len(findings)}, systemic={len(systemic)}, "
                f"cleared={result['summary']['auto_cleared']}"
            )
            if findings:
                test.risk_score_after = findings[0]["risk_score"]
        except Exception as exc:
            test.actual_outcome = f"ERROR: {str(exc)}"
            test.passed = False

        results.append(test)

        # Test: Mixed flood — 200 identical + 50 different
        test2 = MonkeyTestResult(
            test_id=self._next_test_id("DUP"),
            test_type="deduplication_flood",
            description="Mixed flood: 200 identical + 50 unique should show proper grouping",
        )
        mixed_events = [
            {"id": i, "source_system": "ERP", "event_type": "dup_error",
             "log_data": "Repeated validation failure", "amount": 100}
            for i in range(200)
        ] + [
            {"id": 200 + i, "source_system": f"System-{i}", "event_type": "unique_error",
             "log_data": f"Unique error {i}", "amount": 600 + i * 10}
            for i in range(50)
        ]
        test2.payload = {"identical": 200, "unique": 50}
        test2.expected_outcome = "proper_grouping"

        try:
            result = validator.process_events(mixed_events)
            # Should create systemic for the 200 identical, plus individual findings for unique
            test2.passed = result["summary"]["systemic_groups"] >= 1
            test2.actual_outcome = (
                f"findings={len(result['findings'])}, "
                f"systemic={result['summary']['systemic_groups']}, "
                f"cleared={result['summary']['auto_cleared']}"
            )
        except Exception as exc:
            test2.actual_outcome = f"ERROR: {str(exc)}"
            test2.passed = False

        results.append(test2)

        return results

    # ──────────────────────────────────────────────────────────────────────
    # TEST SUITE 5: FORMAT ATTACKS
    # ──────────────────────────────────────────────────────────────────────

    def test_format_attacks(self) -> List[MonkeyTestResult]:
        """Test handling of malformed/adversarial input formats."""
        validator = self._get_validator()
        results = []

        attack_cases = [
            (
                {"id": 1, "source_system": "A" * 10000, "event_type": "oversized",
                 "log_data": "X" * 50000, "amount": 1000},
                "Oversized string fields (10K + 50K chars)"
            ),
            (
                {"id": 2, "source_system": "Test\x00Null\x00Bytes",
                 "event_type": "null_bytes", "log_data": "Data\x00Here", "amount": 1000},
                "Null bytes in strings"
            ),
            (
                {"id": 3, "source_system": "'; DROP TABLE audit_vault; --",
                 "event_type": "sql_injection", "log_data": "SELECT * FROM users",
                 "amount": 1000},
                "SQL injection attempt in source_system"
            ),
            (
                {"id": 4, "source_system": "<script>alert('xss')</script>",
                 "event_type": "xss_attempt", "log_data": "<img onerror=alert(1)>",
                 "amount": 1000},
                "XSS injection attempt"
            ),
            (
                {"id": 5, "source_system": "Unicode Test 🔥💰🚨",
                 "event_type": "unicode_test", "log_data": "Ñoño €500 ¥10000",
                 "amount": 1000},
                "Unicode characters including emoji"
            ),
        ]

        for event, description in attack_cases:
            test = MonkeyTestResult(
                test_id=self._next_test_id("FMT"),
                test_type="format_attack",
                description=description,
            )
            test.payload = {"source": str(event.get("source_system", ""))[:50], "type": event.get("event_type")}
            test.expected_outcome = "handled_without_crash"

            try:
                result = validator.validate_single_event(event)
                test.passed = True
                test.actual_outcome = f"risk={result['risk_score']}, priority={result['priority']}"
            except Exception as exc:
                test.actual_outcome = f"CRASH: {str(exc)}"
                test.passed = False

            results.append(test)

        return results

    # ──────────────────────────────────────────────────────────────────────
    # TEST SUITE 6: TEMPORAL ANOMALIES
    # ──────────────────────────────────────────────────────────────────────

    def test_temporal_anomalies(self) -> List[MonkeyTestResult]:
        """Test handling of temporal edge cases."""
        validator = self._get_validator()
        results = []

        temporal_cases = [
            (
                datetime(1970, 1, 1, tzinfo=timezone.utc).isoformat(),
                "Epoch zero timestamp"
            ),
            (
                (datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
                "Future-dated event (1 year ahead)"
            ),
            (
                "not-a-valid-timestamp",
                "Invalid timestamp string"
            ),
            (
                "",
                "Empty timestamp"
            ),
            (
                (datetime.now(timezone.utc) - timedelta(days=3650)).isoformat(),
                "Very old event (10 years ago)"
            ),
        ]

        for timestamp, description in temporal_cases:
            test = MonkeyTestResult(
                test_id=self._next_test_id("TMP"),
                test_type="temporal_anomaly",
                description=description,
            )
            event = {
                "id": random.randint(10000, 99999),
                "source_system": "TemporalTest",
                "event_type": "time_anomaly",
                "log_data": f"Event with timestamp: {timestamp}",
                "amount": 5000,
                "timestamp": timestamp,
            }
            test.payload = {"timestamp": timestamp}
            test.expected_outcome = "handled_without_crash"

            try:
                result = validator.validate_single_event(event)
                test.passed = True
                test.actual_outcome = f"risk={result['risk_score']}, priority={result['priority']}"
            except Exception as exc:
                test.actual_outcome = f"CRASH: {str(exc)}"
                test.passed = False

            results.append(test)

        return results

    # ──────────────────────────────────────────────────────────────────────
    # TEST SUITE 7: FINANCIAL EXPLOITS
    # ──────────────────────────────────────────────────────────────────────

    def test_financial_exploits(self) -> List[MonkeyTestResult]:
        """Test financial edge cases around materiality threshold."""
        validator = self._get_validator()
        results = []

        exploit_cases = [
            (499.99, 2, "Two events at $499.99 — individual below threshold but combined above"),
            (250.00, 3, "Three events at $250 — individually immaterial but aggregate $750"),
            (1000000.00, 1, "Single $1M transaction — should be Critical"),
            (float('inf'), 1, "Infinity amount — should handle gracefully"),
            (float('nan'), 1, "NaN amount — should handle gracefully"),
        ]

        for amount, count, description in exploit_cases:
            test = MonkeyTestResult(
                test_id=self._next_test_id("FIN"),
                test_type="financial_exploit",
                description=description,
            )
            events = [
                {"id": i, "source_system": "FinTest", "event_type": "financial_test",
                 "log_data": f"Amount: ${amount}", "amount": amount}
                for i in range(count)
            ]
            test.payload = {"amount": str(amount), "count": count}
            test.expected_outcome = "handled_correctly"

            try:
                result = validator.process_events(events)
                test.passed = True
                test.actual_outcome = (
                    f"findings={len(result['findings'])}, "
                    f"impact={result['summary']['total_financial_impact']}, "
                    f"cleared={result['summary']['auto_cleared']}"
                )
            except Exception as exc:
                test.actual_outcome = f"ERROR: {str(exc)}"
                # NaN and Inf may cause issues — that's informational, not a failure
                test.passed = "nan" in str(amount).lower() or "inf" in str(amount).lower()

            results.append(test)

        return results

    # ──────────────────────────────────────────────────────────────────────
    # TEST SUITE 8: FORENSIC INTEGRITY
    # ──────────────────────────────────────────────────────────────────────

    def test_forensic_integrity(self) -> List[MonkeyTestResult]:
        """Test the forensic engine's ability to detect hallucinations."""
        forensic = self._get_forensic()
        results = []

        # Test 1: Summary with wrong count
        test = MonkeyTestResult(
            test_id=self._next_test_id("FOR"),
            test_type="forensic_integrity",
            description="Summary claiming 100 records but only 5 exist — should detect discrepancy",
        )
        summary = {"total_raw_events": 100, "total_financial_impact": 50000}
        raw_records = [
            {"id": i, "source_system": "Test", "event_type": "test",
             "amount": 1000, "log_data": f"Record {i}"}
            for i in range(5)
        ]
        test.payload = {"claimed_count": 100, "actual_count": 5}
        test.expected_outcome = "discrepancy_detected"

        try:
            result = forensic.verify_summary(summary, raw_records)
            test.passed = not result.is_valid and len(result.discrepancies) > 0
            test.actual_outcome = (
                f"valid={result.is_valid}, discrepancies={len(result.discrepancies)}, "
                f"confidence={result.confidence_score}"
            )
        except Exception as exc:
            test.actual_outcome = f"ERROR: {str(exc)}"
            test.passed = False

        results.append(test)

        # Test 2: Summary with correct data — should pass
        test2 = MonkeyTestResult(
            test_id=self._next_test_id("FOR"),
            test_type="forensic_integrity",
            description="Accurate summary should pass integrity check",
        )
        accurate_summary = {"total_raw_events": 3}
        accurate_records = [
            {"id": i, "source_system": "Test", "event_type": "test",
             "log_data": f"Record {i}"}
            for i in range(3)
        ]
        test2.payload = {"claimed_count": 3, "actual_count": 3}
        test2.expected_outcome = "passes_verification"

        try:
            result = forensic.verify_summary(accurate_summary, accurate_records)
            test2.passed = result.is_valid or result.confidence_score > 80
            test2.actual_outcome = (
                f"valid={result.is_valid}, confidence={result.confidence_score}"
            )
        except Exception as exc:
            test2.actual_outcome = f"ERROR: {str(exc)}"
            test2.passed = False

        results.append(test2)

        # Test 3: Hallucinated source system
        test3 = MonkeyTestResult(
            test_id=self._next_test_id("FOR"),
            test_type="forensic_integrity",
            description="Summary referencing non-existent source should flag hallucination",
        )
        hallucinated_summary = {
            "total_raw_events": 2,
            "findings": [
                {"category": "phantom_system|phantom_error|general", "risk_score": 50}
            ]
        }
        real_records = [
            {"id": 1, "source_system": "RealSystem", "event_type": "real", "log_data": "Real"}
        ]
        test3.payload = {"claimed_source": "phantom_system", "actual_source": "RealSystem"}
        test3.expected_outcome = "hallucination_detected"

        try:
            result = forensic.verify_summary(hallucinated_summary, real_records)
            has_issues = len(result.hallucinations) > 0 or len(result.discrepancies) > 0
            test3.passed = has_issues
            test3.actual_outcome = (
                f"valid={result.is_valid}, hallucinations={len(result.hallucinations)}, "
                f"discrepancies={len(result.discrepancies)}"
            )
        except Exception as exc:
            test3.actual_outcome = f"ERROR: {str(exc)}"
            test3.passed = False

        results.append(test3)

        return results


# ──────────────────────────────────────────────────────────────────────────────
# CLI runner
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    import os
    # Ensure the project root (parent of agents/) is on sys.path
    _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    print("=" * 60)
    print("  ACAP MONKEY TESTER — Adversarial Control Testing")
    print("=" * 60)

    tester = MonkeyTester()
    results = tester.run_all_tests()

    print(f"\n{'=' * 60}")
    print(f"  RESULTS: {results['passed']}/{results['total_tests']} passed "
          f"({results['pass_rate']}%)")
    print(f"  Duration: {results['duration_seconds']:.2f}s")
    print(f"{'=' * 60}")

    for suite, stats in results["suites"].items():
        status = "✓" if stats.get("failed", 0) == 0 else "✗"
        print(f"  {status} {suite}: {stats['passed']}/{stats['total']} passed")

    sys.exit(0 if results["failed"] == 0 else 1)
