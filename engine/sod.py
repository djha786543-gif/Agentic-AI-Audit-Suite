"""
engine/sod.py
─────────────
Segregation of Duties (SoD) Conflict Detection Engine.

Supports SAP, Oracle, NetSuite, and generic ERP role structures.
Detects toxic combinations of permissions/roles per COSO + PCAOB standards.
"""
from __future__ import annotations
import itertools
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# SOD CONFLICT MATRIX
# Format: (role_keyword_a, role_keyword_b) → (conflict_type, risk_level, description)
# Keywords are matched case-insensitively against role/permission names
# ─────────────────────────────────────────────────────────────────────────────
SOD_MATRIX: Dict[tuple, dict] = {
    # ── Accounts Payable ──────────────────────────────────────────────────────
    ("create_vendor", "pay_vendor"):          {"type": "AP_SOD_001", "risk": "CRITICAL", "desc": "User can create vendors AND initiate payments — ghost vendor fraud risk"},
    ("vendor_create", "vendor_payment"):      {"type": "AP_SOD_001", "risk": "CRITICAL", "desc": "User can create vendors AND initiate payments — ghost vendor fraud risk"},
    ("create_vendor", "approve_payment"):     {"type": "AP_SOD_002", "risk": "CRITICAL", "desc": "User can create vendors AND approve payments"},
    ("vendor_setup", "payment_approve"):      {"type": "AP_SOD_002", "risk": "CRITICAL", "desc": "User can set up vendors AND approve payments"},
    ("po_create", "po_approve"):              {"type": "AP_SOD_003", "risk": "HIGH",     "desc": "User can create AND approve purchase orders"},
    ("create_po", "approve_po"):              {"type": "AP_SOD_003", "risk": "HIGH",     "desc": "User can create AND approve purchase orders"},
    ("invoice_entry", "payment_release"):     {"type": "AP_SOD_004", "risk": "HIGH",     "desc": "User can enter invoices AND release payments"},
    ("invoice_create", "payment_approve"):    {"type": "AP_SOD_004", "risk": "HIGH",     "desc": "User can create invoices AND approve payments"},
    ("goods_receipt", "invoice_approve"):     {"type": "AP_SOD_005", "risk": "MEDIUM",   "desc": "User performs goods receipt AND approves invoices — bypass three-way match"},

    # ── Accounts Receivable ───────────────────────────────────────────────────
    ("create_customer", "apply_payment"):     {"type": "AR_SOD_001", "risk": "CRITICAL", "desc": "User can create customers AND apply cash receipts — lapping fraud risk"},
    ("credit_memo", "cash_receipt"):          {"type": "AR_SOD_002", "risk": "HIGH",     "desc": "User can issue credit memos AND post cash receipts"},
    ("write_off", "cash_apply"):              {"type": "AR_SOD_003", "risk": "HIGH",     "desc": "User can write off balances AND apply cash — concealment risk"},
    ("invoice_create", "cash_receipt"):       {"type": "AR_SOD_004", "risk": "HIGH",     "desc": "User can create invoices AND receive cash payments"},
    ("credit_limit", "sales_order"):          {"type": "AR_SOD_005", "risk": "MEDIUM",   "desc": "User can modify credit limits AND enter sales orders"},

    # ── General Ledger / Journal Entries ──────────────────────────────────────
    ("journal_create", "journal_approve"):    {"type": "GL_SOD_001", "risk": "CRITICAL", "desc": "User can create AND approve journal entries — unauthorized adjustments"},
    ("je_create", "je_post"):                 {"type": "GL_SOD_001", "risk": "CRITICAL", "desc": "User can create AND post journal entries"},
    ("journal_entry", "journal_post"):        {"type": "GL_SOD_001", "risk": "CRITICAL", "desc": "User can enter AND post journal entries"},
    ("account_create", "journal_post"):       {"type": "GL_SOD_002", "risk": "HIGH",     "desc": "User can create GL accounts AND post journal entries"},
    ("period_close", "journal_create"):       {"type": "GL_SOD_003", "risk": "HIGH",     "desc": "User can open/close periods AND create journal entries"},
    ("intercompany", "journal_approve"):      {"type": "GL_SOD_004", "risk": "HIGH",     "desc": "User initiates intercompany transactions AND approves journal entries"},

    # ── Payroll ───────────────────────────────────────────────────────────────
    ("payroll_setup", "payroll_approve"):     {"type": "PR_SOD_001", "risk": "CRITICAL", "desc": "User can set up payroll AND approve payroll runs — ghost employee risk"},
    ("employee_create", "payroll_process"):   {"type": "PR_SOD_002", "risk": "CRITICAL", "desc": "User can add employees AND process payroll"},
    ("salary_change", "payroll_approve"):     {"type": "PR_SOD_003", "risk": "HIGH",     "desc": "User can change salaries AND approve payroll"},
    ("timesheet_approve", "payroll_run"):     {"type": "PR_SOD_004", "risk": "HIGH",     "desc": "User approves timesheets AND runs payroll processing"},
    ("bank_account", "payroll_payment"):      {"type": "PR_SOD_005", "risk": "CRITICAL", "desc": "User can change bank accounts AND process payroll payments"},

    # ── Inventory / Fixed Assets ──────────────────────────────────────────────
    ("inventory_adjust", "inventory_count"):  {"type": "INV_SOD_001","risk": "HIGH",     "desc": "User can adjust inventory AND perform physical counts"},
    ("asset_create", "asset_dispose"):        {"type": "FA_SOD_001", "risk": "HIGH",     "desc": "User can add AND retire fixed assets"},
    ("asset_value", "asset_dispose"):         {"type": "FA_SOD_002", "risk": "HIGH",     "desc": "User can change asset values AND dispose assets"},

    # ── IT / System Administration ────────────────────────────────────────────
    ("user_create", "role_assign"):           {"type": "IT_SOD_001", "risk": "HIGH",     "desc": "User can create accounts AND assign roles/permissions"},
    ("user_admin", "audit_log"):              {"type": "IT_SOD_002", "risk": "HIGH",     "desc": "User administers users AND manages audit logs — log tampering risk"},
    ("system_config", "change_approve"):      {"type": "IT_SOD_003", "risk": "HIGH",     "desc": "User modifies system config AND approves their own changes"},
    ("code_deploy", "change_approve"):        {"type": "IT_SOD_004", "risk": "CRITICAL", "desc": "Developer can deploy code AND approve production changes"},
    ("basis_admin", "financial_posting"):     {"type": "IT_SOD_005", "risk": "CRITICAL", "desc": "SAP Basis admin has access to financial posting transactions"},

    # ── Procurement ───────────────────────────────────────────────────────────
    ("rfq_create", "rfq_approve"):            {"type": "PROC_SOD_001","risk":"HIGH",      "desc": "User can create AND approve RFQ/bids — bid rigging risk"},
    ("contract_create","contract_approve"):   {"type": "PROC_SOD_002","risk":"HIGH",      "desc": "User can create AND approve contracts"},
    ("requisition", "po_approve"):            {"type": "PROC_SOD_003","risk":"MEDIUM",    "desc": "User creates requisitions AND approves resulting POs"},
}


@dataclass
class SoDFinding:
    user_id: str
    role_a: str
    role_b: str
    conflict_type: str
    risk_level: str
    description: str
    control_id: str = "ITGC-SOD"
    recommendation: str = ""
    source_system: str = "Unknown"

    def __post_init__(self):
        if not self.recommendation:
            self.recommendation = self._build_recommendation()

    def _build_recommendation(self) -> str:
        if self.risk_level == "CRITICAL":
            return f"IMMEDIATE ACTION: Remove one of the conflicting roles from user {self.user_id}. Obtain documented business justification if exception is required. Implement compensating monitoring control."
        elif self.risk_level == "HIGH":
            return f"Remove conflicting access from {self.user_id} within 30 days. Document exception if business-justified. Add to next access review cycle."
        else:
            return f"Review access for {self.user_id} in next quarterly access review. Document business justification if dual access is required."

    def to_dict(self) -> dict:
        return {
            "control_id": self.control_id,
            "user_id": self.user_id,
            "role_a": self.role_a,
            "role_b": self.role_b,
            "conflict_type": self.conflict_type,
            "risk_level": self.risk_level,
            "description": self.description,
            "recommendation": self.recommendation,
            "source_system": self.source_system,
            "status": "EXCEPTION",
        }


def _normalize(s: str) -> str:
    """Lowercase, strip, replace spaces/hyphens with underscores."""
    return s.lower().strip().replace(" ", "_").replace("-", "_").replace(".", "_")


def _role_matches_keyword(role: str, keyword: str) -> bool:
    """Check if a role name contains the keyword (fuzzy match)."""
    r = _normalize(role)
    k = _normalize(keyword)
    return k in r


def detect_sod_conflicts(
    user_roles: Dict[str, List[str]],
    source_system: str = "ERP"
) -> List[SoDFinding]:
    """
    Detect SoD conflicts for a dict of {user_id: [role1, role2, ...]}

    Args:
        user_roles: Dictionary mapping user IDs to their list of roles/permissions
        source_system: Name of the source system (SAP, Oracle, etc.)

    Returns:
        List of SoDFinding objects for each conflict detected
    """
    findings: List[SoDFinding] = []

    for user_id, roles in user_roles.items():
        if not roles or len(roles) < 2:
            continue

        # Check every pair of roles against the SoD matrix
        for (role_a, role_b) in itertools.combinations(roles, 2):
            for (kw_a, kw_b), conflict in SOD_MATRIX.items():
                a_matches_kw_a = _role_matches_keyword(role_a, kw_a)
                a_matches_kw_b = _role_matches_keyword(role_a, kw_b)
                b_matches_kw_a = _role_matches_keyword(role_b, kw_a)
                b_matches_kw_b = _role_matches_keyword(role_b, kw_b)

                conflict_found = (
                    (a_matches_kw_a and b_matches_kw_b) or
                    (a_matches_kw_b and b_matches_kw_a)
                )

                if conflict_found:
                    # Avoid duplicates for same user/conflict type
                    existing = [
                        f for f in findings
                        if f.user_id == user_id and f.conflict_type == conflict["type"]
                    ]
                    if not existing:
                        findings.append(SoDFinding(
                            user_id=str(user_id),
                            role_a=role_a,
                            role_b=role_b,
                            conflict_type=conflict["type"],
                            risk_level=conflict["risk"],
                            description=conflict["desc"],
                            source_system=source_system,
                        ))

    logger.info(
        "SoD engine: scanned %d users, found %d conflicts",
        len(user_roles), len(findings)
    )
    return findings


def summarize_sod_results(findings: List[SoDFinding]) -> dict:
    """Build a summary dict for the API response."""
    total = len(findings)
    by_risk = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for f in findings:
        by_risk[f.risk_level] = by_risk.get(f.risk_level, 0) + 1

    unique_users = len(set(f.user_id for f in findings))
    unique_types = len(set(f.conflict_type for f in findings))

    return {
        "total_conflicts": total,
        "unique_users_affected": unique_users,
        "unique_conflict_types": unique_types,
        "by_risk_level": by_risk,
        "pass": total == 0,
        "control_area": "Segregation of Duties",
        "standard_ref": "COSO 2013 CC10.3 · SOX 404 · PCAOB AS2201",
    }
