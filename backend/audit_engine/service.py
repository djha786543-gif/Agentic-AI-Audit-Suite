"""Audit engine adapter layer."""
from __future__ import annotations

from typing import Any

from engine.runner import run_audit_engine


def run_engine(parsed_data: dict[str, Any], source_system: str = "Uploaded File") -> dict[str, Any]:
    return run_audit_engine(parsed_data=parsed_data, source_system=source_system)
