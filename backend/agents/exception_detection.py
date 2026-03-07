"""Exception Detection Agent."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def run(payload: dict[str, Any]) -> dict[str, Any]:
    findings = payload.get("findings", []) or []
    open_exceptions = sum(1 for f in findings if str(f.get("status", "open")).lower() in {"open", "high", "critical"})
    return {
        "decision_summary": f"Detected {open_exceptions} open/high-priority exception candidates.",
        "confidence_score": 0.8 if open_exceptions else 0.62,
        "reasoning_trace": "Exception signal based on finding status severity/state values.",
        "data_sources": ["findings"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
