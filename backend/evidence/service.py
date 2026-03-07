"""Evidence adapter service."""
from __future__ import annotations

from typing import Any


def normalize_evidence_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "audit_id": payload.get("audit_id"),
        "control_id": payload.get("control_id"),
        "uploaded_by": payload.get("uploaded_by"),
        "timestamp": payload.get("timestamp"),
        "hash_signature": payload.get("hash_signature"),
        "verification_status": payload.get("verification_status", "pending"),
    }
