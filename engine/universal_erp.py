"""
engine/universal_erp.py
───────────────────────
Tier-1 Universal ERP Engine support:
  - source-to-report lineage indexing
  - referential integrity checks before control execution
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Dict, Iterable, List, Tuple


@dataclass
class IntegrityIssue:
    issue_type: str
    key: str
    detail: str
    severity: str = "HIGH"

    def to_dict(self) -> Dict[str, str]:
        return {
            "issue_type": self.issue_type,
            "key": self.key,
            "detail": self.detail,
            "severity": self.severity,
        }


def _normalize_id(value: Any) -> str:
    return str(value or "").strip().lower()


def build_lineage_index(parsed_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Create a deterministic lineage index keyed by row fingerprint."""
    index: Dict[str, Dict[str, Any]] = {}
    for sheet_name, sheet_data in parsed_data.get("sheets", {}).items():
        records = sheet_data.get("records", [])
        data_type = sheet_data.get("data_type", "unknown")
        for rec in records:
            payload = {k: v for k, v in rec.items() if k != "_lineage"}
            fingerprint = sha256(str(sorted(payload.items())).encode("utf-8")).hexdigest()
            lineage = dict(rec.get("_lineage") or {})
            lineage.setdefault("sheet", sheet_name)
            lineage.setdefault("erp_table", data_type)
            index[fingerprint] = lineage
    return index


def attach_lineage_to_findings(findings: List[Dict[str, Any]], lineage_index: Dict[str, Dict[str, Any]]) -> None:
    """
    Attach best-effort lineage pointer to finding evidence payload.
    This does not mutate source records, only finding dictionaries.
    """
    for finding in findings:
        evidence = dict(finding.get("evidence") or {})
        # Try explicit row-fingerprint if already provided by an engine.
        row_fp = evidence.get("row_fingerprint")
        if isinstance(row_fp, str) and row_fp in lineage_index:
            evidence["lineage"] = lineage_index[row_fp]
            finding["evidence"] = evidence
            continue

        # Fall back to deterministic hash from key evidence fields.
        candidate_payload = {
            "entity": finding.get("entity"),
            "field1": finding.get("field1"),
            "field2": finding.get("field2"),
            "rule": finding.get("rule"),
        }
        fallback_fp = sha256(str(sorted(candidate_payload.items())).encode("utf-8")).hexdigest()
        if fallback_fp in lineage_index:
            evidence["lineage"] = lineage_index[fallback_fp]
        else:
            evidence.setdefault("lineage", {"erp_table": "unknown", "row_number": None})
        finding["evidence"] = evidence


def referential_integrity_check(
    active_users: Iterable[Dict[str, Any]],
    hr_master_users: Iterable[Dict[str, Any]],
) -> Tuple[bool, List[Dict[str, str]]]:
    """
    Validate that every active user can be referenced in HR master data.

    Returns:
      (passed, list_of_issues)
    """
    hr_ids = {
        _normalize_id(r.get("user_id") or r.get("employee_id") or r.get("username"))
        for r in hr_master_users
    }
    hr_ids.discard("")

    issues: List[IntegrityIssue] = []
    for row in active_users:
        uid = _normalize_id(row.get("user_id") or row.get("username") or row.get("employee_id"))
        if not uid:
            continue
        if uid not in hr_ids:
            issues.append(
                IntegrityIssue(
                    issue_type="MISSING_HR_REFERENCE",
                    key=uid,
                    detail=f"Active user '{uid}' not found in HR master data.",
                    severity="CRITICAL",
                )
            )

    return len(issues) == 0, [i.to_dict() for i in issues]
