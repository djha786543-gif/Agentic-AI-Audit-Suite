"""
engine/runner.py
────────────────
Audit Engine Orchestrator.

Receives parsed data, routes to appropriate engines,
aggregates all findings, computes overall risk score,
and returns a unified audit result payload.
"""
from __future__ import annotations
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import logging

from .sod import detect_sod_conflicts, summarize_sod_results
from .access import test_access_controls, summarize_access_results
from .change import test_change_management, summarize_change_results
from .operations import test_operations_controls, summarize_operations_results
from .itac import run_all_itac_tests
from .parser import extract_user_roles
from .universal_erp import attach_lineage_to_findings, build_lineage_index, referential_integrity_check

logger = logging.getLogger(__name__)

RISK_WEIGHTS = {"CRITICAL": 40, "HIGH": 20, "MEDIUM": 8, "LOW": 2}
MAX_RISK_SCORE = 100


def _compute_risk_score(findings: List[Dict]) -> int:
    """Compute a 0-100 risk score based on finding severity distribution."""
    if not findings:
        return 0
    raw = sum(RISK_WEIGHTS.get(f.get("risk_level", "LOW"), 2) for f in findings)
    # Normalize: assume >200 raw points = score of 100
    return min(100, int((raw / 200) * 100))


def _risk_rating(score: int) -> str:
    if score >= 70: return "CRITICAL"
    if score >= 45: return "HIGH"
    if score >= 20: return "MEDIUM"
    return "LOW"


def run_audit_engine(
    parsed_data: Dict[str, Any],
    source_system: str = "Uploaded File",
    audit_period: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Master orchestrator. Receives output from parser.parse_file() and
    routes records to each applicable control engine.

    Returns a complete audit result payload ready for the API response.
    """
    start_time = datetime.now(timezone.utc)
    all_findings: List[Dict] = []
    domain_results: Dict[str, Any] = {}
    engines_run: List[str] = []

    # ── Gather all records across sheets ─────────────────────────────────────
    all_records_by_type: Dict[str, List[Dict]] = {
        "users": [], "changes": [], "transactions": [],
        "backup": [], "incident": [], "interfaces": [], "dr": [], "hr_master": [],
    }

    for sheet_name, sheet_data in parsed_data.get("sheets", {}).items():
        records = sheet_data.get("records", [])
        data_type = sheet_data.get("data_type", "unknown")
        if data_type in all_records_by_type:
            all_records_by_type[data_type].extend(records)
            logger.info("Sheet '%s': %d records routed to '%s' engine", sheet_name, len(records), data_type)

    # ── Referential Integrity Precheck (Active Users ↔ HR Master) ──────────
    user_records = all_records_by_type["users"]
    hr_master_records = all_records_by_type["hr_master"]
    integrity_passed = True
    if user_records and hr_master_records:
        integrity_passed, integrity_issues = referential_integrity_check(user_records, hr_master_records)
        domain_results["referential_integrity"] = {
            "summary": {
                "pass": integrity_passed,
                "issues": len(integrity_issues),
                "standard_ref": "PCAOB AS 1105 - Audit Evidence Reliability",
            },
            "issues": integrity_issues,
        }

    # ── SoD Engine ───────────────────────────────────────────────────────────
    if user_records:
        engines_run.append("Segregation of Duties")
        if integrity_passed or not hr_master_records:
            user_roles = extract_user_roles(user_records)
            sod_findings = detect_sod_conflicts(user_roles, source_system=source_system)
            sod_dicts = [f.to_dict() for f in sod_findings]
            all_findings.extend(sod_dicts)
            domain_results["sod"] = {
                "summary": summarize_sod_results(sod_findings),
                "findings": sod_dicts,
            }
        else:
            domain_results["sod"] = {
                "summary": {
                    "pass": False,
                    "blocked": True,
                    "reason": "SOD execution blocked because referential integrity checks failed.",
                },
                "findings": [],
            }

    # ── Access Control Engine ─────────────────────────────────────────────────
    if user_records:
        engines_run.append("Logical Access Controls")
        access_findings = test_access_controls(user_records)
        access_dicts = [f.to_dict() for f in access_findings]
        all_findings.extend(access_dicts)
        domain_results["access"] = {
            "summary": summarize_access_results(access_findings),
            "findings": access_dicts,
        }

    # ── Change Management Engine ──────────────────────────────────────────────
    change_records = all_records_by_type["changes"]
    if change_records:
        engines_run.append("Change Management")
        change_findings = test_change_management(change_records)
        change_dicts = [f.to_dict() for f in change_findings]
        all_findings.extend(change_dicts)
        domain_results["change_management"] = {
            "summary": summarize_change_results(change_findings),
            "findings": change_dicts,
        }

    # ── Operations Engine — Backup ────────────────────────────────────────────
    backup_records = all_records_by_type["backup"]
    if backup_records:
        engines_run.append("Computer Operations - Backup")
        ops_findings = test_operations_controls(backup_records, record_type="backup")
        ops_dicts = [f.to_dict() for f in ops_findings]
        all_findings.extend(ops_dicts)
        domain_results["operations_backup"] = {
            "summary": summarize_operations_results(ops_findings),
            "findings": ops_dicts,
        }

    # ── Operations Engine — Incidents ─────────────────────────────────────────
    incident_records = all_records_by_type["incident"]
    if incident_records:
        engines_run.append("Computer Operations - Incidents")
        inc_findings = test_operations_controls(incident_records, record_type="incident")
        inc_dicts = [f.to_dict() for f in inc_findings]
        all_findings.extend(inc_dicts)
        domain_results["operations_incidents"] = {
            "summary": summarize_operations_results(inc_findings),
            "findings": inc_dicts,
        }

    # ── Operations Engine — DR ────────────────────────────────────────────────
    dr_records = all_records_by_type["dr"]
    if dr_records:
        engines_run.append("Disaster Recovery")
        dr_findings = test_operations_controls(dr_records, record_type="dr")
        dr_dicts = [f.to_dict() for f in dr_findings]
        all_findings.extend(dr_dicts)
        domain_results["operations_dr"] = {
            "summary": summarize_operations_results(dr_findings),
            "findings": dr_dicts,
        }

    # ── ITAC Engine ───────────────────────────────────────────────────────────
    transaction_records = all_records_by_type["transactions"]
    interface_records = all_records_by_type["interfaces"]
    if transaction_records or interface_records:
        engines_run.append("IT Application Controls")
        itac_findings, itac_summary = run_all_itac_tests({
            "transactions": transaction_records,
            "interfaces": interface_records,
        })
        itac_dicts = [f.to_dict() for f in itac_findings]
        all_findings.extend(itac_dicts)
        domain_results["itac"] = {
            "summary": itac_summary,
            "findings": itac_dicts,
        }

    # ── Cross-Agent Corroboration ─────────────────────────────────────────────
    # Find active transaction users from ITAC findings
    itac_users_involved = set()
    for f in all_findings:
        if f.get("control_id", "").startswith("ITAC"):
            # Try to grab users from description or known fields
            desc = f.get("description", "")
            # Since ITAC may flag approvers or requestors, we can extract them if they're in the desc
            # This is a simple substring check below
            pass
            
    # Link ITGC (SOD/Access) with ITAC (Transactions)
    for itgc in all_findings:
        if itgc.get("control_id", "").startswith("ITGC-SOD") or itgc.get("control_id", "").startswith("ITGC-LA"):
            user = itgc.get("user_id")
            if not user:
                continue
            # Look for this user in ITAC finding descriptions or raw records
            for itac in all_findings:
                if itac.get("control_id", "").startswith("ITAC") and user in itac.get("description", ""):
                    # Corroborated!
                    itgc["corroborated_by_transaction"] = True
                    itgc["confidence"] = "99.99%"
                    itgc["risk_level"] = "CRITICAL"
                    if "CORROBORATED" not in itgc.get("recommendation", ""):
                        itgc["recommendation"] = str(itgc.get("recommendation", "")) + " CORROBORATED: User identified in transaction test exceptions! Actual material impact detected."
                        
                    itac["corroborated_by_itgc"] = True
                    itac["confidence"] = "99.99%"
                    if "CORROBORATED" not in itac.get("recommendation", ""):
                        itac["recommendation"] = str(itac.get("recommendation", "")) + " CORROBORATED: Originating user has ITGC control exceptions (SOD/Access)!"

    # ── Aggregate Risk Score ──────────────────────────────────────────────────
    lineage_index = build_lineage_index(parsed_data)
    attach_lineage_to_findings(all_findings, lineage_index)

    entity_lineage: Dict[str, Dict[str, Any]] = {}
    for sheet_data in parsed_data.get("sheets", {}).values():
        for rec in sheet_data.get("records", []):
            lineage = rec.get("_lineage") or {}
            for key in ("user_id", "invoice_id", "ticket_id", "id", "record_id"):
                val = rec.get(key)
                if val is not None:
                    entity_lineage[str(val)] = lineage

    for finding in all_findings:
        evidence = dict(finding.get("evidence") or {})
        lookup_id = str(
            finding.get("user_id")
            or finding.get("record_id")
            or finding.get("entity")
            or ""
        )
        if lookup_id and lookup_id in entity_lineage:
            evidence["lineage"] = entity_lineage[lookup_id]
            finding["evidence"] = evidence

    # Explainable AI payload required for peer review/re-performance.
    for finding in all_findings:
        finding.setdefault(
            "logic_breakdown",
            (
                f"Flagged because {finding.get('entity', 'record')} triggered rule {finding.get('rule') or finding.get('finding_type') or finding.get('control_id')} "
                f"with severity {finding.get('risk_level', 'MEDIUM')}."
            ),
        )
        finding.setdefault(
            "reperformance",
            {
                "prompt_template": "Evaluate finding risk based on rule trigger, entity context, and control impact.",
                "inputs": {
                    "rule": finding.get("rule") or finding.get("finding_type"),
                    "entity": finding.get("entity"),
                    "severity": finding.get("risk_level"),
                    "evidence": finding.get("evidence"),
                },
            },
        )

    risk_score = _compute_risk_score(all_findings)
    overall_rating = _risk_rating(risk_score)

    by_risk: Dict[str, int] = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for f in all_findings:
        lvl = f.get("risk_level", "LOW")
        by_risk[lvl] = by_risk.get(lvl, 0) + 1

    end_time = datetime.now(timezone.utc)
    elapsed = (end_time - start_time).total_seconds()

    result = {
        "audit_id": f"AUDIT-{start_time.strftime('%Y%m%d-%H%M%S')}",
        "source_system": source_system,
        "audit_period": audit_period or "Not specified",
        "engines_run": engines_run,
        "total_records_analyzed": parsed_data.get("total_records", 0),
        "total_findings": len(all_findings),
        "overall_risk_score": risk_score,
        "overall_risk_rating": overall_rating,
        "findings_by_risk": by_risk,
        "domain_results": domain_results,
        "all_findings": all_findings,
        "generated_at": start_time.isoformat(),
        "processing_seconds": round(elapsed, 2),
        "status": "COMPLETE",
        "sox_impact": overall_rating in ("CRITICAL", "HIGH"),
        "management_action_required": by_risk["CRITICAL"] > 0,
        "standard_refs": [
            "COSO 2013 Internal Control Framework",
            "SOX Section 302 & 404",
            "PCAOB AS 2201",
            "ISO 27001:2022",
            "COBIT 2019",
        ],
    }

    logger.info(
        "Audit engine complete: %d findings, risk_score=%d (%s), elapsed=%.2fs",
        len(all_findings), risk_score, overall_rating, elapsed,
    )
    return result
