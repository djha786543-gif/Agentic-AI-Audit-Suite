"""Enterprise agent orchestrator (additive service layer)."""
from __future__ import annotations

from typing import Any

from backend.agents import (
    audit_reporting,
    control_mapping,
    evidence_analysis,
    exception_detection,
    process_analysis,
    risk_identification,
)

def run_orchestration(input_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        "process_analysis": process_analysis.run(input_payload),
        "risk_identification": risk_identification.run(input_payload),
        "control_mapping": control_mapping.run(input_payload),
        "evidence_analysis": evidence_analysis.run(input_payload),
        "exception_detection": exception_detection.run(input_payload),
        "audit_reporting": audit_reporting.run(input_payload),
    }
