"""
core/sqlite_store.py
────────────────────
Layer 3 — SQLite Integration for Audit Intelligence Storage

Replaces JSON file storage with SQLite to resolve:
  - File Locking issues during concurrent access
  - JSONDecodeErrors during high-volume stress tests
  - Data corruption from partial writes

This module provides a thread-safe, WAL-mode SQLite database for storing:
  - Processed audit findings (from SOXValidator)
  - Forensic verification results (from ForensicEngine)
  - Aggregation state (deduplication groups, materiality decisions)
  - Monkey tester adversarial results

The PostgreSQL vault remains the primary evidence store.
SQLite is used for the INTELLIGENCE LAYER only — processed results,
risk scores, and forensic reasoning.

Usage:
    from core.sqlite_store import AuditIntelligenceStore
    store = AuditIntelligenceStore()
    store.save_findings(findings)
    store.save_verification(result)
"""

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default database path — alongside the project root
DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "audit_intelligence.db"
)


class AuditIntelligenceStore:
    """
    Thread-safe SQLite store for audit intelligence data.

    Uses WAL mode for concurrent read/write without file locking issues.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._local = threading.local()
        self._init_schema()

    def _get_conn(self) -> sqlite3.Connection:
        """Get a thread-local SQLite connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30,
            )
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA busy_timeout=10000")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_schema(self):
        """Create tables if they don't exist."""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS audit_findings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                finding_id TEXT UNIQUE NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                risk_score REAL NOT NULL DEFAULT 0,
                priority TEXT NOT NULL DEFAULT 'Low',
                financial_impact REAL DEFAULT 0,
                occurrence_count INTEGER DEFAULT 1,
                is_systemic INTEGER DEFAULT 0,
                materiality_status TEXT DEFAULT 'unknown',
                auditor_reasoning TEXT,
                control_type TEXT DEFAULT 'monitoring',
                raw_event_ids TEXT DEFAULT '[]',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                batch_id TEXT
            );

            CREATE TABLE IF NOT EXISTS forensic_verifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                verification_type TEXT NOT NULL,
                target_id TEXT,
                is_valid INTEGER NOT NULL DEFAULT 1,
                confidence_score REAL DEFAULT 100.0,
                discrepancies TEXT DEFAULT '[]',
                math_errors TEXT DEFAULT '[]',
                hallucinations TEXT DEFAULT '[]',
                warnings TEXT DEFAULT '[]',
                total_issues INTEGER DEFAULT 0,
                checked_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS executive_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                headline TEXT NOT NULL,
                risk_posture TEXT NOT NULL,
                critical_count INTEGER DEFAULT 0,
                high_count INTEGER DEFAULT 0,
                systemic_count INTEGER DEFAULT 0,
                total_financial_exposure REAL DEFAULT 0,
                highest_risk_score REAL DEFAULT 0,
                top_findings TEXT DEFAULT '[]',
                recommendations TEXT DEFAULT '[]',
                integrity_check TEXT DEFAULT '{}',
                generated_at TEXT NOT NULL DEFAULT (datetime('now')),
                verification_status TEXT DEFAULT 'pending'
            );

            CREATE TABLE IF NOT EXISTS aggregation_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_signature TEXT UNIQUE NOT NULL,
                event_count INTEGER DEFAULT 0,
                total_financial_impact REAL DEFAULT 0,
                is_systemic INTEGER DEFAULT 0,
                first_seen TEXT NOT NULL DEFAULT (datetime('now')),
                last_seen TEXT NOT NULL DEFAULT (datetime('now')),
                auto_cleared INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS monkey_test_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id TEXT UNIQUE NOT NULL,
                test_type TEXT NOT NULL,
                payload TEXT,
                expected_outcome TEXT,
                actual_outcome TEXT,
                passed INTEGER DEFAULT 0,
                risk_score_before REAL,
                risk_score_after REAL,
                notes TEXT,
                executed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_findings_priority ON audit_findings(priority);
            CREATE INDEX IF NOT EXISTS idx_findings_risk ON audit_findings(risk_score DESC);
            CREATE INDEX IF NOT EXISTS idx_findings_batch ON audit_findings(batch_id);
            CREATE INDEX IF NOT EXISTS idx_verifications_type ON forensic_verifications(verification_type);
            CREATE INDEX IF NOT EXISTS idx_aggregation_signature ON aggregation_state(group_signature);
            CREATE INDEX IF NOT EXISTS idx_monkey_test_type ON monkey_test_results(test_type);
        """)
        conn.commit()
        logger.info("sqlite_store.schema_initialized  path=%s", self.db_path)

    # ──────────────────────────────────────────────────────────────────────
    # FINDINGS STORAGE
    # ──────────────────────────────────────────────────────────────────────

    def save_findings(self, findings: List[Dict[str, Any]], batch_id: Optional[str] = None) -> int:
        """
        Save processed audit findings to SQLite.
        Uses INSERT OR REPLACE to handle deduplication by finding_id.
        Returns count of saved findings.
        """
        conn = self._get_conn()
        saved = 0
        batch = batch_id or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        for finding in findings:
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO audit_findings
                    (finding_id, category, description, risk_score, priority,
                     financial_impact, occurrence_count, is_systemic,
                     materiality_status, auditor_reasoning, control_type,
                     raw_event_ids, updated_at, batch_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    finding.get("finding_id"),
                    finding.get("category", ""),
                    finding.get("description", ""),
                    finding.get("risk_score", 0),
                    finding.get("priority", "Low"),
                    finding.get("financial_impact", 0),
                    finding.get("occurrence_count", 1),
                    1 if finding.get("is_systemic") else 0,
                    finding.get("materiality_status", "unknown"),
                    finding.get("auditor_reasoning", ""),
                    finding.get("control_type", "monitoring"),
                    json.dumps(finding.get("raw_event_ids", [])),
                    datetime.now(timezone.utc).isoformat(),
                    batch,
                ))
                saved += 1
            except Exception as exc:
                logger.error("sqlite_store.save_finding_error  id=%s  err=%s",
                             finding.get("finding_id"), str(exc))

        conn.commit()
        logger.info("sqlite_store.findings_saved  count=%d  batch=%s", saved, batch)
        return saved

    def get_findings(
        self,
        priority: Optional[str] = None,
        min_risk_score: Optional[float] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Retrieve findings with optional filtering."""
        conn = self._get_conn()
        query = "SELECT * FROM audit_findings WHERE 1=1"
        params = []

        if priority:
            query += " AND priority = ?"
            params.append(priority)
        if min_risk_score is not None:
            query += " AND risk_score >= ?"
            params.append(min_risk_score)

        query += " ORDER BY risk_score DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get_findings_summary(self) -> Dict[str, Any]:
        """Get aggregate statistics for the dashboard."""
        conn = self._get_conn()

        total = conn.execute("SELECT COUNT(*) FROM audit_findings").fetchone()[0]
        critical = conn.execute(
            "SELECT COUNT(*) FROM audit_findings WHERE priority = 'Critical'"
        ).fetchone()[0]
        high = conn.execute(
            "SELECT COUNT(*) FROM audit_findings WHERE priority = 'High'"
        ).fetchone()[0]
        medium = conn.execute(
            "SELECT COUNT(*) FROM audit_findings WHERE priority = 'Medium'"
        ).fetchone()[0]
        low = conn.execute(
            "SELECT COUNT(*) FROM audit_findings WHERE priority = 'Low'"
        ).fetchone()[0]
        systemic = conn.execute(
            "SELECT COUNT(*) FROM audit_findings WHERE is_systemic = 1"
        ).fetchone()[0]
        total_impact = conn.execute(
            "SELECT COALESCE(SUM(financial_impact), 0) FROM audit_findings"
        ).fetchone()[0]
        avg_risk = conn.execute(
            "SELECT COALESCE(AVG(risk_score), 0) FROM audit_findings"
        ).fetchone()[0]
        max_risk = conn.execute(
            "SELECT COALESCE(MAX(risk_score), 0) FROM audit_findings"
        ).fetchone()[0]

        return {
            "total_findings": total,
            "critical": critical,
            "high": high,
            "medium": medium,
            "low": low,
            "systemic_groups": systemic,
            "total_financial_impact": round(total_impact, 2),
            "average_risk_score": round(avg_risk, 1),
            "highest_risk_score": round(max_risk, 1),
        }

    # ──────────────────────────────────────────────────────────────────────
    # VERIFICATION STORAGE
    # ──────────────────────────────────────────────────────────────────────

    def save_verification(
        self,
        verification_type: str,
        result: Dict[str, Any],
        target_id: Optional[str] = None,
    ) -> int:
        """Save a forensic verification result."""
        conn = self._get_conn()
        cursor = conn.execute("""
            INSERT INTO forensic_verifications
            (verification_type, target_id, is_valid, confidence_score,
             discrepancies, math_errors, hallucinations, warnings,
             total_issues, checked_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            verification_type,
            target_id,
            1 if result.get("is_valid", True) else 0,
            result.get("confidence_score", 100.0),
            json.dumps(result.get("discrepancies", [])),
            json.dumps(result.get("math_errors", [])),
            json.dumps(result.get("hallucinations", [])),
            json.dumps(result.get("warnings", [])),
            result.get("total_issues", 0),
            result.get("checked_at", datetime.now(timezone.utc).isoformat()),
        ))
        conn.commit()
        return cursor.lastrowid

    def get_recent_verifications(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent verification results."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM forensic_verifications ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    # ──────────────────────────────────────────────────────────────────────
    # EXECUTIVE SUMMARY STORAGE
    # ──────────────────────────────────────────────────────────────────────

    def save_executive_summary(self, summary: Dict[str, Any]) -> int:
        """Save an executive summary."""
        conn = self._get_conn()
        cursor = conn.execute("""
            INSERT INTO executive_summaries
            (headline, risk_posture, critical_count, high_count,
             systemic_count, total_financial_exposure, highest_risk_score,
             top_findings, recommendations, integrity_check,
             generated_at, verification_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            summary.get("headline", ""),
            summary.get("risk_posture", "Unknown"),
            summary.get("critical_count", 0),
            summary.get("high_count", 0),
            summary.get("systemic_count", 0),
            summary.get("total_financial_exposure", 0),
            summary.get("highest_risk_score", 0),
            json.dumps(summary.get("top_findings", [])),
            json.dumps(summary.get("recommendations", [])),
            json.dumps(summary.get("integrity_check", {})),
            summary.get("generated_at", datetime.now(timezone.utc).isoformat()),
            summary.get("verification_status", "pending"),
        ))
        conn.commit()
        return cursor.lastrowid

    def get_latest_summary(self) -> Optional[Dict[str, Any]]:
        """Get the most recent executive summary."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM executive_summaries ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row:
            result = self._row_to_dict(row)
            # Parse JSON fields
            for field in ["top_findings", "recommendations", "integrity_check"]:
                if field in result and isinstance(result[field], str):
                    try:
                        result[field] = json.loads(result[field])
                    except (json.JSONDecodeError, TypeError):
                        pass
            return result
        return None

    # ──────────────────────────────────────────────────────────────────────
    # AGGREGATION STATE
    # ──────────────────────────────────────────────────────────────────────

    def update_aggregation_state(
        self,
        group_signature: str,
        event_count: int,
        financial_impact: float,
        is_systemic: bool,
        auto_cleared: bool = False,
    ):
        """Update the aggregation state for a group of events."""
        conn = self._get_conn()
        conn.execute("""
            INSERT INTO aggregation_state
            (group_signature, event_count, total_financial_impact,
             is_systemic, last_seen, auto_cleared)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(group_signature) DO UPDATE SET
                event_count = event_count + excluded.event_count,
                total_financial_impact = total_financial_impact + excluded.total_financial_impact,
                is_systemic = excluded.is_systemic,
                last_seen = excluded.last_seen,
                auto_cleared = excluded.auto_cleared
        """, (
            group_signature,
            event_count,
            financial_impact,
            1 if is_systemic else 0,
            datetime.now(timezone.utc).isoformat(),
            1 if auto_cleared else 0,
        ))
        conn.commit()

    # ──────────────────────────────────────────────────────────────────────
    # MONKEY TEST RESULTS
    # ──────────────────────────────────────────────────────────────────────

    def save_monkey_test(self, test_result: Dict[str, Any]) -> int:
        """Save an adversarial monkey test result."""
        conn = self._get_conn()
        cursor = conn.execute("""
            INSERT OR REPLACE INTO monkey_test_results
            (test_id, test_type, payload, expected_outcome,
             actual_outcome, passed, risk_score_before,
             risk_score_after, notes, executed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            test_result.get("test_id"),
            test_result.get("test_type", "unknown"),
            json.dumps(test_result.get("payload", {})),
            test_result.get("expected_outcome", ""),
            test_result.get("actual_outcome", ""),
            1 if test_result.get("passed") else 0,
            test_result.get("risk_score_before"),
            test_result.get("risk_score_after"),
            test_result.get("notes", ""),
            test_result.get("executed_at", datetime.now(timezone.utc).isoformat()),
        ))
        conn.commit()
        return cursor.lastrowid

    def get_monkey_test_summary(self) -> Dict[str, Any]:
        """Get aggregate monkey test statistics."""
        conn = self._get_conn()
        total = conn.execute("SELECT COUNT(*) FROM monkey_test_results").fetchone()[0]
        passed = conn.execute(
            "SELECT COUNT(*) FROM monkey_test_results WHERE passed = 1"
        ).fetchone()[0]
        failed = total - passed

        return {
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": round(passed / total * 100, 1) if total > 0 else 0.0,
        }

    # ──────────────────────────────────────────────────────────────────────
    # DASHBOARD DATA
    # ──────────────────────────────────────────────────────────────────────

    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get all data needed for the dashboard Intelligence Center.
        Single call returns everything the UI needs.
        """
        return {
            "findings_summary": self.get_findings_summary(),
            "top_findings": self.get_findings(limit=10),
            "latest_summary": self.get_latest_summary(),
            "recent_verifications": self.get_recent_verifications(limit=5),
            "monkey_test_summary": self.get_monkey_test_summary(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ──────────────────────────────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a sqlite3.Row to a regular dict."""
        return dict(row)

    def close(self):
        """Close the thread-local connection."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
