"""
api/v1/endpoints/intelligence.py
─────────────────────────────────
API endpoints for the Auditor Intelligence Layer.

Exposes the SOXValidator, ForensicEngine, and SQLite Intelligence Store
through RESTful endpoints consumed by the dashboard.

Endpoints:
  GET  /intelligence/dashboard     — Full dashboard data
  GET  /intelligence/findings      — Filtered audit findings
  POST /intelligence/process       — Process raw events through the intelligence pipeline
  POST /intelligence/verify        — Run forensic integrity check
  GET  /intelligence/summary       — Latest executive summary
  POST /intelligence/monkey-test   — Run adversarial monkey tests
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query

from core.sox_validator import SOXValidator
from core.forensic_engine import ForensicEngine
from core.sqlite_store import AuditIntelligenceStore

logger = logging.getLogger(__name__)
router = APIRouter()

# Singleton instances — reused across requests
_validator = SOXValidator()
_forensic = ForensicEngine()
_store = AuditIntelligenceStore()


@router.get("/dashboard")
def get_intelligence_dashboard():
    """
    Full dashboard data endpoint — returns everything the
    Intelligence Center UI needs in a single call.
    """
    try:
        data = _store.get_dashboard_data()
        data["status"] = "connected"
        data["engine_version"] = "2.0.0"
        return data
    except Exception as e:
        logger.error("intelligence.dashboard_error  %s", str(e))
        return {
            "status": "degraded",
            "error": str(e),
            "findings_summary": {
                "total_findings": 0, "critical": 0, "high": 0,
                "medium": 0, "low": 0, "systemic_groups": 0,
                "total_financial_impact": 0,
                "average_risk_score": 0, "highest_risk_score": 0,
            },
            "top_findings": [],
            "latest_summary": None,
            "recent_verifications": [],
            "monkey_test_summary": {"total_tests": 0, "passed": 0, "failed": 0, "pass_rate": 0},
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/findings")
def get_findings(
    priority: Optional[str] = Query(None, description="Filter by priority: Critical, High, Medium, Low"),
    min_risk: Optional[float] = Query(None, description="Minimum risk score (0-100)"),
    limit: int = Query(50, description="Maximum findings to return"),
):
    """Get filtered audit findings from the intelligence store."""
    try:
        findings = _store.get_findings(
            priority=priority,
            min_risk_score=min_risk,
            limit=limit,
        )
        return {
            "findings": findings,
            "count": len(findings),
            "filters": {
                "priority": priority,
                "min_risk_score": min_risk,
                "limit": limit,
            },
        }
    except Exception as e:
        logger.error("intelligence.findings_error  %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process")
def process_events(events: List[Dict[str, Any]]):
    """
    Process raw audit events through the full intelligence pipeline:
    1. SOXValidator: Deduplicate → Materiality Filter → Risk Score
    2. ForensicEngine: Generate Auditor Reasoning
    3. SQLite Store: Persist findings
    4. ForensicEngine: Self-verify the generated summary
    """
    try:
        # Step 1: Process through SOXValidator
        result = _validator.process_events(events)

        # Step 2: Save findings to SQLite
        if result["findings"]:
            _store.save_findings(result["findings"])

        # Step 3: Generate and verify executive summary
        summary = _forensic.generate_executive_summary(
            result["findings"],
            result["summary"],
        )
        _store.save_executive_summary(summary)

        # Step 4: Save verification
        if summary.get("integrity_check"):
            _store.save_verification(
                verification_type="executive_summary",
                result=summary["integrity_check"],
            )

        return {
            "status": "processed",
            "pipeline_result": result,
            "executive_summary": summary,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error("intelligence.process_error  %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify")
def verify_integrity(
    summary: Dict[str, Any],
    raw_records: Optional[List[Dict[str, Any]]] = None,
):
    """
    Run forensic integrity check on an AI-generated summary.
    Cross-references against raw data to flag hallucinations and math errors.
    """
    try:
        records = raw_records or []
        result = _forensic.verify_summary(summary, records)

        # Save verification result
        _store.save_verification(
            verification_type="manual_verification",
            result=result.to_dict(),
        )

        return result.to_dict()
    except Exception as e:
        logger.error("intelligence.verify_error  %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
def get_latest_summary():
    """Get the most recent executive summary with integrity check."""
    try:
        summary = _store.get_latest_summary()
        if summary:
            return {"status": "found", "summary": summary}
        return {
            "status": "no_summary",
            "message": "No executive summary generated yet. Run /intelligence/process first.",
        }
    except Exception as e:
        logger.error("intelligence.summary_error  %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/monkey-test")
def run_monkey_tests():
    """
    Run the adversarial monkey tester suite.
    Returns pass/fail results for all test categories.
    """
    try:
        from agents.monkey_tester import MonkeyTester
        tester = MonkeyTester(
            sox_validator=_validator,
            forensic_engine=_forensic,
            sqlite_store=_store,
        )
        results = tester.run_all_tests()
        return results
    except Exception as e:
        logger.error("intelligence.monkey_test_error  %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate-event")
def validate_single_event(event: Dict[str, Any]):
    """
    Quick risk assessment for a single audit event.
    Returns risk score, priority, and materiality status.
    """
    try:
        result = _validator.validate_single_event(event)
        reasoning = _forensic.generate_reasoning(
            event,
            control_type="detective",
            financial_impact=result["financial_impact"],
        )
        result["auditor_reasoning"] = reasoning
        return result
    except Exception as e:
        logger.error("intelligence.validate_error  %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))
