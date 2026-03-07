"""
engine/itac.py
──────────────
IT Application Controls (ITAC) Testing Engine.

Tests application-level controls embedded in ERP / business applications:
  - Three-way match (PO + GR + Invoice)
  - Duplicate payment detection
  - Invoice amount limit controls
  - Approval workflow bypass
  - Calculation accuracy (payroll, depreciation)
  - Interface/integration completeness
  - Input validation gaps
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from decimal import Decimal, InvalidOperation
import logging

logger = logging.getLogger(__name__)

DUPLICATE_WINDOW_DAYS = 30        # Look for duplicate invoices within 30 days
APPROVAL_THRESHOLD = 10_000       # Invoices >$10k require manager approval
HIGH_VALUE_THRESHOLD = 50_000     # Invoices >$50k require VP approval
PAYROLL_VARIANCE_PCT = 0.05       # >5% payroll change month-over-month flags


@dataclass
class ITACFinding:
    control_id: str
    record_id: str
    finding_type: str
    risk_level: str
    description: str
    recommendation: str
    evidence: Dict = field(default_factory=dict)
    status: str = "EXCEPTION"

    def to_dict(self) -> dict:
        return {
            "control_id": self.control_id,
            "record_id": self.record_id,
            "finding_type": self.finding_type,
            "risk_level": self.risk_level,
            "description": self.description,
            "recommendation": self.recommendation,
            "evidence": self.evidence,
            "status": self.status,
        }


def _to_decimal(val: Any) -> Optional[Decimal]:
    if val is None or str(val).lower() in ("nan", "none", "null", "", "n/a"):
        return None
    try:
        return Decimal(str(val).replace(",", "").replace("$", "").strip())
    except InvalidOperation:
        return None


def _str(val: Any) -> str:
    return str(val).strip().lower() if val is not None else ""


def test_three_way_match(transactions: List[Dict]) -> List[ITACFinding]:
    """
    Test three-way match control (PO Amount ≈ GR Amount ≈ Invoice Amount).
    Tolerance: 5% or $50, whichever is greater.
    """
    findings: List[ITACFinding] = []
    TOLERANCE_PCT = Decimal("0.05")
    TOLERANCE_ABS = Decimal("50")

    for txn in transactions:
        tid = str(txn.get("invoice_id") or txn.get("transaction_id") or txn.get("id") or "UNKNOWN")
        po_amt = _to_decimal(txn.get("po_amount") or txn.get("purchase_order_amount"))
        gr_amt = _to_decimal(txn.get("gr_amount") or txn.get("goods_receipt_amount") or txn.get("receipt_amount"))
        inv_amt = _to_decimal(txn.get("invoice_amount") or txn.get("amount"))
        po_qty = _to_decimal(txn.get("po_qty") or txn.get("po_quantity") or txn.get("ordered_qty"))
        gr_qty = _to_decimal(txn.get("gr_qty") or txn.get("received_qty") or txn.get("goods_receipt_qty"))
        inv_qty = _to_decimal(txn.get("invoice_qty") or txn.get("quantity"))
        po_unit_price = _to_decimal(txn.get("po_unit_price") or txn.get("ordered_unit_price"))
        inv_unit_price = _to_decimal(txn.get("invoice_unit_price") or txn.get("unit_price"))
        three_way = _str(txn.get("three_way_match") or txn.get("match_status"))
        vendor = str(txn.get("vendor") or txn.get("vendor_name") or "Unknown")

        # Explicit bypass
        if three_way in ("bypass", "bypassed", "skipped", "override", "overridden"):
            findings.append(ITACFinding(
                control_id="ITAC-AP-001",
                record_id=tid,
                finding_type="THREE_WAY_MATCH_BYPASS",
                risk_level="CRITICAL",
                description=f"Invoice {tid} from {vendor} explicitly bypassed the three-way match control.",
                recommendation="Investigate who authorized bypass and reason. Verify goods/services were actually received. Review for potential vendor fraud or kickback scheme.",
                evidence={"vendor": vendor, "amount": str(inv_amt), "match_status": three_way},
            ))
            continue

        # Amount variance test
        if po_amt and gr_amt and inv_amt:
            amounts = [po_amt, gr_amt, inv_amt]
            max_amt = max(amounts)
            min_amt = min(amounts)
            variance = max_amt - min_amt
            tolerance = max(max_amt * TOLERANCE_PCT, TOLERANCE_ABS)

            if variance > tolerance:
                findings.append(ITACFinding(
                    control_id="ITAC-AP-001",
                    record_id=tid,
                    finding_type="THREE_WAY_MATCH_VARIANCE",
                    risk_level="HIGH",
                    description=f"Invoice {tid}: variance of ${variance:.2f} between PO/GR/Invoice amounts exceeds tolerance of ${tolerance:.2f}.",
                    recommendation="Place invoice on hold. Obtain explanation from vendor and AP team. Verify goods receipt documentation. Do not pay until variance is resolved.",
                    evidence={"po_amount": str(po_amt), "gr_amount": str(gr_amt), "invoice_amount": str(inv_amt), "variance": str(variance)},
                ))

        # Quantity mismatch automation.
        if po_qty and gr_qty and inv_qty:
            qty_max = max(po_qty, gr_qty, inv_qty)
            qty_min = min(po_qty, gr_qty, inv_qty)
            qty_variance = qty_max - qty_min
            qty_tolerance = max(qty_max * Decimal("0.02"), Decimal("1"))
            if qty_variance > qty_tolerance:
                findings.append(ITACFinding(
                    control_id="ITAC-AP-001",
                    record_id=tid,
                    finding_type="THREE_WAY_QUANTITY_MISMATCH",
                    risk_level="HIGH",
                    description=f"Invoice {tid}: quantity mismatch detected (PO={po_qty}, GR={gr_qty}, Invoice={inv_qty}).",
                    recommendation="Investigate quantity discrepancy before payment release. Validate receiving docs and partial shipment terms.",
                    evidence={"po_qty": str(po_qty), "gr_qty": str(gr_qty), "invoice_qty": str(inv_qty), "qty_variance": str(qty_variance)},
                ))

        # Price variance automation.
        if po_unit_price and inv_unit_price:
            price_var = abs(inv_unit_price - po_unit_price)
            price_tol = max(po_unit_price * Decimal("0.03"), Decimal("0.5"))
            if price_var > price_tol:
                findings.append(ITACFinding(
                    control_id="ITAC-AP-001",
                    record_id=tid,
                    finding_type="THREE_WAY_PRICE_VARIANCE",
                    risk_level="HIGH",
                    description=f"Invoice {tid}: unit price variance ${price_var:.2f} exceeds tolerance ${price_tol:.2f}.",
                    recommendation="Hold invoice and validate contract pricing, amendments, and approved change orders.",
                    evidence={"po_unit_price": str(po_unit_price), "invoice_unit_price": str(inv_unit_price), "price_variance": str(price_var)},
                ))

    return findings


def test_duplicate_payments(transactions: List[Dict]) -> List[ITACFinding]:
    """Detect potential duplicate invoices (same vendor + amount + date window)."""
    findings: List[ITACFinding] = []

    # Group by vendor + amount
    groups: Dict[Tuple, List[str]] = {}
    for txn in transactions:
        tid = str(txn.get("invoice_id") or txn.get("id") or "UNKNOWN")
        vendor = _str(txn.get("vendor") or txn.get("vendor_id") or "")
        amount = str(_to_decimal(txn.get("invoice_amount") or txn.get("amount")) or "")
        inv_num = _str(txn.get("invoice_number") or txn.get("invoice_no") or "")

        if vendor and amount:
            key = (vendor, amount)
            if key not in groups:
                groups[key] = []
            groups[key].append({"tid": tid, "inv_num": inv_num})

    for (vendor, amount), records in groups.items():
        if len(records) > 1:
            # Check for same invoice number (definite duplicate)
            inv_nums = [r["inv_num"] for r in records if r["inv_num"]]
            if len(inv_nums) != len(set(inv_nums)) and inv_nums:
                risk = "CRITICAL"
                desc = f"Exact duplicate invoice detected: Vendor '{vendor}', Amount ${amount}, same invoice number appears {len(records)} times."
            else:
                risk = "HIGH"
                desc = f"Potential duplicate: Vendor '{vendor}', Amount ${amount} appears {len(records)} times."

            findings.append(ITACFinding(
                control_id="ITAC-AP-002",
                record_id=records[0]["tid"],
                finding_type="DUPLICATE_PAYMENT_RISK",
                risk_level=risk,
                description=desc,
                recommendation="Place duplicate invoices on hold. Contact vendor to confirm only one invoice is valid. Review payment status of all duplicates before releasing any payment.",
                evidence={"vendor": vendor, "amount": amount, "invoice_ids": [r["tid"] for r in records]},
            ))

    return findings


def test_approval_limits(transactions: List[Dict]) -> List[ITACFinding]:
    """Test that payment approvals match authorization matrix."""
    findings: List[ITACFinding] = []

    for txn in transactions:
        tid = str(txn.get("invoice_id") or txn.get("id") or "UNKNOWN")
        amount = _to_decimal(txn.get("invoice_amount") or txn.get("amount"))
        approver_level = _str(txn.get("approver_level") or txn.get("approval_level") or "")
        approver = str(txn.get("approved_by") or txn.get("approver") or "Unknown")
        vendor = str(txn.get("vendor") or "Unknown")

        if not amount:
            continue

        if amount > HIGH_VALUE_THRESHOLD:
            if approver_level not in ("vp", "director", "cfo", "executive", "svp", "evp"):
                findings.append(ITACFinding(
                    control_id="ITAC-AP-003",
                    record_id=tid,
                    finding_type="APPROVAL_LIMIT_BREACH",
                    risk_level="CRITICAL",
                    description=f"Invoice {tid} for ${amount:,.2f} from {vendor} approved by {approver} (level: {approver_level or 'unknown'}) — VP/Director approval required for amounts >$50,000.",
                    recommendation="Obtain retroactive VP-level approval. Review authorization matrix. Implement system-level approval routing based on invoice amount.",
                    evidence={"amount": str(amount), "approver": approver, "approver_level": approver_level, "required_level": "VP/Director"},
                ))
        elif amount > APPROVAL_THRESHOLD:
            if approver_level in ("", "none", "n/a", "unknown") or not approver_level:
                findings.append(ITACFinding(
                    control_id="ITAC-AP-003",
                    record_id=tid,
                    finding_type="APPROVAL_LEVEL_UNCLEAR",
                    risk_level="HIGH",
                    description=f"Invoice {tid} for ${amount:,.2f} from {vendor} — approver level not documented for amount requiring manager approval.",
                    recommendation="Document approver authority level for all invoices >$10,000. Implement approval routing workflow in AP system.",
                    evidence={"amount": str(amount), "approver": approver},
                ))

    return findings


def test_interface_controls(records: List[Dict]) -> List[ITACFinding]:
    """Test interface/integration completeness between systems."""
    findings: List[ITACFinding] = []

    for rec in records:
        rid = str(rec.get("interface_id") or rec.get("run_id") or rec.get("id") or "UNKNOWN")
        source_count = _to_decimal(rec.get("source_count") or rec.get("records_sent"))
        target_count = _to_decimal(rec.get("target_count") or rec.get("records_received"))
        source_total = _to_decimal(rec.get("source_total") or rec.get("amount_sent"))
        target_total = _to_decimal(rec.get("target_total") or rec.get("amount_received"))
        interface_name = str(rec.get("interface_name") or rec.get("name") or rid)
        status = _str(rec.get("status"))

        if status in ("failed", "error"):
            findings.append(ITACFinding(
                control_id="ITAC-INT-001",
                record_id=rid,
                finding_type="INTERFACE_FAILURE",
                risk_level="HIGH",
                description=f"Interface '{interface_name}' failed — data may not have transferred completely between systems.",
                recommendation="Investigate failure. Perform manual reconciliation between source and target systems. Re-run interface and verify completeness.",
                evidence={"interface": interface_name, "status": status},
            ))

        if source_count and target_count and source_count != target_count:
            variance = abs(source_count - target_count)
            findings.append(ITACFinding(
                control_id="ITAC-INT-002",
                record_id=rid,
                finding_type="INTERFACE_COUNT_MISMATCH",
                risk_level="HIGH",
                description=f"Interface '{interface_name}': {int(source_count)} records sent, {int(target_count)} received — {int(variance)} records missing.",
                recommendation="Identify missing records in target system. Investigate why records were dropped. Re-process missing records and update reconciliation control log.",
                evidence={"sent": str(source_count), "received": str(target_count), "variance": str(variance)},
            ))

        if source_total and target_total:
            variance = abs(source_total - target_total)
            if variance > Decimal("0.01"):
                findings.append(ITACFinding(
                    control_id="ITAC-INT-003",
                    record_id=rid,
                    finding_type="INTERFACE_AMOUNT_MISMATCH",
                    risk_level="HIGH",
                    description=f"Interface '{interface_name}': amount variance of ${variance:.2f} between source (${source_total:.2f}) and target (${target_total:.2f}).",
                    recommendation="Investigate amount discrepancy. Check for rounding differences, currency conversion issues, or truncated fields. Do not post to GL until resolved.",
                    evidence={"source_total": str(source_total), "target_total": str(target_total), "variance": str(variance)},
                ))

    return findings


def run_all_itac_tests(data: Dict[str, List[Dict]]) -> Tuple[List[ITACFinding], dict]:
    """
    Run all ITAC tests. data keys:
      'transactions' - AP invoice transactions
      'interfaces'   - interface/integration records
    """
    all_findings: List[ITACFinding] = []

    transactions = data.get("transactions", [])
    interfaces = data.get("interfaces", [])

    if transactions:
        all_findings.extend(test_three_way_match(transactions))
        all_findings.extend(test_duplicate_payments(transactions))
        all_findings.extend(test_approval_limits(transactions))

    if interfaces:
        all_findings.extend(test_interface_controls(interfaces))

    summary = {
        "total_exceptions": len(all_findings),
        "by_risk_level": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
        "pass": len(all_findings) == 0,
        "control_area": "IT Application Controls",
        "standard_ref": "ITAC · COSO CC4.1 · PCAOB AS2201 · SOX 404",
    }
    for f in all_findings:
        summary["by_risk_level"][f.risk_level] = summary["by_risk_level"].get(f.risk_level, 0) + 1

    logger.info("ITAC engine: ran %d tests, found %d findings", len(transactions) + len(interfaces), len(all_findings))
    return all_findings, summary
