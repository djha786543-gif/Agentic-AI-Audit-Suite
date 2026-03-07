"""Workflow transition helper service."""
from __future__ import annotations

from typing import Any


def record_transition(state_from: str, state_to: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "stage_from": state_from,
        "stage_to": state_to,
        "metadata": metadata or {},
    }
