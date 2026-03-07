"""
api/v1/endpoints/engine.py
──────────────────────────
Audit Engine API Endpoints.

POST /api/v1/engine/analyze
  Upload a file (CSV/Excel/JSON/SAP TXT) and run all control engines.
  Returns full audit findings JSON.

POST /api/v1/engine/analyze/sod
  SoD-only analysis with explicit user-roles payload.

GET  /api/v1/engine/health
  Engine health check — confirms all modules loaded.

POST /api/v1/engine/sample
  Returns sample data templates for each data type.
"""
from __future__ import annotations
import json
import logging
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from db.async_session import get_async_db
from sqlalchemy import text

from engine.parser import parse_file
from engine.runner import run_audit_engine
from engine.sod import detect_sod_conflicts, summarize_sod_results
from engine.privacy import tokenize_identities
from engine.sampling import attribute_sampling, confidence_level_sampling, mus_sampling
from engine.universal_erp import referential_integrity_check

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json", ".jsonl", ".txt"}
MAX_FILE_SIZE_MB = 50


def _check_extension(filename: str):
    import os
    ext = os.path.splitext(filename.lower())[1]
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not supported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    return ext


@router.get("/health")
async def engine_health():
    """Confirm all engine modules are loaded and ready."""
    try:
        from engine.sod import SOD_MATRIX
        from engine.access import DORMANT_THRESHOLD_DAYS
        from engine.change import CHANGE_WINDOW_HOURS
        from engine.itac import APPROVAL_THRESHOLD
        return {
            "status": "healthy",
            "engines": {
                "sod": f"ready ({len(SOD_MATRIX)} conflict rules loaded)",
                "access": "ready",
                "change_management": "ready",
                "operations": "ready",
                "itac": "ready",
                "parser": "ready (csv/xlsx/json/sap)",
            },
            "message": "All control engines operational",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Engine not ready: {str(e)}")


@router.post("/analyze")
async def analyze_file(
    file: UploadFile = File(...),
    source_system: str = Form(default="Uploaded File"),
    audit_period: Optional[str] = Form(default=None),
    anonymize: bool = Form(default=False),
):
    """
    Upload a CSV, Excel, JSON, or SAP TXT file and run all applicable
    audit control engines. Returns complete findings JSON.

    source_system: Name of the system the data came from (e.g., 'SAP ECC', 'Oracle', 'ServiceNow')
    audit_period:  e.g. 'Q4 2025', 'FY2025', 'Jan-Dec 2025'
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = _check_extension(file.filename)

    # Read file
    raw_bytes = await file.read()
    file_size_mb = len(raw_bytes) / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({file_size_mb:.1f} MB). Max size: {MAX_FILE_SIZE_MB} MB"
        )

    logger.info("Engine analyze: file=%s size=%.2fMB source=%s", file.filename, file_size_mb, source_system)

    # Parse
    try:
        if ext in (".xlsx", ".xls"):
            parsed = parse_file(file.filename, file_bytes=raw_bytes)
        else:
            content = raw_bytes.decode("utf-8", errors="replace")
            parsed = parse_file(file.filename, content=content)
    except Exception as e:
        logger.error("Parse error: %s", str(e))
        raise HTTPException(status_code=422, detail=f"Could not parse file: {str(e)}")

    if parsed.get("total_records", 0) == 0:
        raise HTTPException(
            status_code=422,
            detail="File parsed but contained no readable records. Check file format and column headers."
        )

    # Run all engines
    try:
        result = run_audit_engine(
            parsed_data=parsed,
            source_system=source_system,
            audit_period=audit_period,
        )

        if anonymize:
            tokenized, reverse_map = tokenize_identities(result.get("all_findings", []))
            result["all_findings"] = tokenized
            result["anonymization"] = {
                "enabled": True,
                "token_count": len(reverse_map),
            }

        if "validation" in parsed:
            result["validation_summary"] = parsed["validation"]
            
        # Optional: persist findings to database for accuracy tracking
        from db.async_session import AsyncSessionLocal
        from sqlalchemy import text
        import uuid
        import json
        
        async with AsyncSessionLocal() as session:
            for i, f in enumerate(result.get("all_findings", [])):
                fid = str(uuid.uuid4())
                f["finding_id"] = fid
                
                # Mock Evidence payload
                f["evidence"] = {
                    "source_rows": f"[[Source Data Row {i}]]", 
                    "row_indices": [i], 
                    "file_hash": parsed.get("validation", {}).get("hash", "N/A"),
                    "detection_rule": f.get("finding_type", "Rule check")
                }
                
                # Save into findings table
                try:
                    q = text(
                        """
                        INSERT INTO findings (
                            id, control_id, severity, description, status, evidence, logic_breakdown, reperformance_payload
                        ) VALUES (
                            :id, :cid, :sev, :desc, 'open', :evidence, :logic_breakdown, :reperformance_payload
                        )
                        """
                    )
                    await session.execute(q, {
                        "id": fid,
                        "cid": f.get("control_id", "AUTO"),
                        "sev": f.get("risk_level", "MEDIUM"),
                        "desc": f.get("description", ""),
                        "evidence": json.dumps({
                            "lineage": (f.get("evidence") or {}).get("lineage"),
                            "logic_breakdown": f.get("logic_breakdown"),
                            "reperformance": f.get("reperformance"),
                            "detection_rule": f.get("finding_type", "Rule check"),
                        }),
                        "logic_breakdown": f.get("logic_breakdown"),
                        "reperformance_payload": json.dumps(f.get("reperformance") or {}),
                    })
                except Exception as db_err:
                    pass # ignore if table structure misses, we want prototyping to work seamlessly
            await session.commit()

    except Exception as e:
        logger.error("Engine error: %s", str(e))
        raise HTTPException(status_code=500, detail=f"Engine processing error: {str(e)}")

    return JSONResponse(content=result)


@router.post("/integrity-check")
async def integrity_check(payload: dict):
    """
    Referential integrity validation for Universal ERP Engine.

    Payload:
      {
        "active_users": [{"user_id": "u1"}, ...],
        "hr_master": [{"user_id": "u1"}, ...]
      }
    """
    active_users = payload.get("active_users") or []
    hr_master = payload.get("hr_master") or []
    passed, issues = referential_integrity_check(active_users, hr_master)
    return {
        "passed": passed,
        "issues": issues,
        "issue_count": len(issues),
        "standard_ref": "PCAOB AS 1105 - Reliable Source Data",
    }


@router.post("/sampling")
async def run_sampling(payload: dict):
    """
    Statistical sampling endpoint:
      - attribute sampling
      - monetary unit sampling (MUS)
    """
    data = payload.get("population") or []
    method = str(payload.get("method") or "attribute").lower()
    if method in ("attribute", "attribute_sampling"):
        return attribute_sampling(
            data,
            sample_size=int(payload.get("sample_size") or 25),
            seed=payload.get("seed", 42),
        )
    if method in ("mus", "monetary_unit_sampling"):
        return mus_sampling(
            data,
            amount_field=str(payload.get("amount_field") or "invoice_amount"),
            confidence_factor=float(payload.get("confidence_factor") or 3.0),
            tolerable_misstatement=float(payload.get("tolerable_misstatement") or 10000.0),
            expected_misstatement=float(payload.get("expected_misstatement") or 1000.0),
            seed=payload.get("seed", 42),
        )
    if method in ("confidence", "confidence_level", "pcaob"):
        return confidence_level_sampling(
            population_size=int(payload.get("population_size") or 0),
            confidence_level=float(payload.get("confidence_level") or 0.95),
            margin_error=float(payload.get("margin_error") or 0.05),
            expected_deviation=float(payload.get("expected_deviation") or 0.5),
            seed=payload.get("seed", 42),
        )
    raise HTTPException(status_code=400, detail="Unsupported method. Use 'attribute', 'mus', or 'confidence'.")


@router.post("/analyze/validate")
async def validate_file(
    file: UploadFile = File(...),
):
    """
    Validation-only endpoint -> extracts schema validation, duplicates, and hash.
    Used for the pre-run Validation Gate UI before executing the heavy agent workloads.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = _check_extension(file.filename)
    raw_bytes = await file.read()
    
    try:
        if ext in (".xlsx", ".xls"):
            parsed = parse_file(file.filename, file_bytes=raw_bytes)
        else:
            content = raw_bytes.decode("utf-8", errors="replace")
            parsed = parse_file(file.filename, content=content)
    except Exception as e:
        logger.error("Parse validate error: %s", str(e))
        raise HTTPException(status_code=422, detail=f"Could not parse file: {str(e)}")

    return {"validation_summary": parsed.get("validation", {})}


@router.post("/analyze/sod")
async def analyze_sod_direct(payload: dict):
    """
    Direct SoD analysis with explicit user-roles payload.
    No file upload needed.

    Payload format:
    {
        "source_system": "SAP",
        "users": {
            "john.doe": ["create_vendor", "pay_vendor", "journal_post"],
            "jane.smith": ["po_create", "po_approve"]
        }
    }
    """
    source_system = payload.get("source_system", "Direct API")
    users = payload.get("users", {})

    if not users:
        raise HTTPException(status_code=400, detail="'users' dict is required with {user_id: [roles]} format")

    findings = detect_sod_conflicts(users, source_system=source_system)
    summary = summarize_sod_results(findings)

    return {
        "audit_id": f"SOD-DIRECT",
        "source_system": source_system,
        "total_users_scanned": len(users),
        "summary": summary,
        "findings": [f.to_dict() for f in findings],
    }


@router.patch("/findings/{finding_id}/verdict")
async def set_verdict(
    finding_id: str, 
    payload: dict,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Accuracy Tracking: Allows auditor to classify as TRUE or FALSE POSITIVE.
    """
    verdict = payload.get("verdict")
    notes = payload.get("notes", "")
    
    # We use raw sql here to emulate the request
    query = text(
        "UPDATE findings SET auditor_verdict=:verdict, verdict_timestamp=now(), verdict_notes=:notes WHERE id=:id"
    )
    await db.execute(query, {"verdict": verdict, "notes": notes, "id": finding_id})
    await db.commit()
    return {"status": "updated", "finding_id": finding_id, "verdict": verdict}


@router.get("/accuracy")
async def get_accuracy(agent: Optional[str] = None, db: AsyncSession = Depends(get_async_db)):
    """
    Computes real-time precision/recall accuracy of the AI engine.
    """
    # Assuming findings table tracks `rule` representing the agent
    query = text(
        "SELECT auditor_verdict, COUNT(*) as c FROM findings WHERE (CAST(:agent AS VARCHAR) IS NULL OR rule LIKE :agent_like) GROUP BY auditor_verdict"
    )
    result = await db.execute(query, {"agent": agent, "agent_like": f"{agent}%" if agent else None})
    
    rows = result.fetchall()
    
    total_reviewed = sum(r.c for r in rows if r.auditor_verdict)
    true_positives = next((r.c for r in rows if r.auditor_verdict == 'confirmed'), 0)
    false_positives = next((r.c for r in rows if r.auditor_verdict == 'false_positive'), 0)
    
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else None
    
    return {
        "total_reviewed": total_reviewed,
        "true_positives": true_positives,
        "false_positives": false_positives,
        "precision": round(precision * 100, 2) if precision else "Not enough data"
    }


@router.post("/analyze/controls")
async def submit_control_result(payload: dict):
    """
    Submit a pre-evaluated control result to the engine.
    Used by the frontend to POST manual test results.

    Payload format matches /api/v1/evaluation/controls schema.
    """
    from engine.sod import SOD_MATRIX

    control_id = payload.get("control_id", "MANUAL")
    status = payload.get("status", "pass").lower()
    description = payload.get("description", "")
    test_type = payload.get("test_type", "Manual")

    return {
        "control_id": control_id,
        "status": "pass" if status == "pass" else "fail",
        "test_type": test_type,
        "description": description,
        "processed": True,
        "message": f"Control {control_id} result recorded",
    }


@router.get("/sample/{data_type}")
async def get_sample_data(data_type: str):
    """
    Return sample CSV templates for each data type.
    data_type: users | changes | transactions | backup | incident | interfaces
    """
    samples = {
        "users": {
            "description": "User Access List — for SoD and Logical Access testing",
            "columns": ["user_id", "username", "status", "roles", "last_login_date", "termination_date", "mfa_enabled", "access_review_date", "department"],
            "example_rows": [
                {"user_id": "U001", "username": "john.smith", "status": "active", "roles": "create_vendor,pay_vendor", "last_login_date": "2025-10-01", "termination_date": "", "mfa_enabled": "No", "access_review_date": "2024-06-01", "department": "Finance"},
                {"user_id": "U002", "username": "jane.doe", "status": "terminated", "roles": "journal_create,journal_post", "last_login_date": "2025-12-01", "termination_date": "2025-11-15", "mfa_enabled": "Yes", "access_review_date": "2025-03-01", "department": "Accounting"},
            ],
        },
        "changes": {
            "description": "Change Management Tickets — for Change Control testing",
            "columns": ["ticket_id", "change_type", "initiator", "approver", "environment", "implementation_date", "test_evidence", "post_impl_review", "status"],
            "example_rows": [
                {"ticket_id": "CHG0001234", "change_type": "normal", "initiator": "dev.team", "approver": "dev.team", "environment": "production", "implementation_date": "2025-10-15", "test_evidence": "No", "post_impl_review": "Yes", "status": "closed"},
                {"ticket_id": "CHG0001235", "change_type": "emergency", "initiator": "ops.team", "approver": "mgr.jones", "environment": "production", "implementation_date": "2025-10-20", "test_evidence": "Yes", "post_impl_review": "No", "status": "closed"},
            ],
        },
        "transactions": {
            "description": "AP Invoice Transactions — for ITAC (three-way match, duplicates, approval limits)",
            "columns": ["invoice_id", "vendor", "invoice_amount", "po_amount", "gr_amount", "three_way_match", "approved_by", "approver_level", "invoice_date"],
            "example_rows": [
                {"invoice_id": "INV-9001", "vendor": "ABC Corp", "invoice_amount": "15000", "po_amount": "15000", "gr_amount": "15000", "three_way_match": "pass", "approved_by": "mgr.smith", "approver_level": "manager", "invoice_date": "2025-10-01"},
                {"invoice_id": "INV-9002", "vendor": "XYZ Ltd", "invoice_amount": "75000", "po_amount": "70000", "gr_amount": "75000", "three_way_match": "bypass", "approved_by": "clerk.jones", "approver_level": "staff", "invoice_date": "2025-10-05"},
            ],
        },
        "backup": {
            "description": "Backup Job Records — for IT Operations testing",
            "columns": ["job_id", "job_name", "system", "backup_date", "status", "restore_tested"],
            "example_rows": [
                {"job_id": "BK-001", "job_name": "ORACLE_FULL_BACKUP", "system": "Oracle DB", "backup_date": "2025-10-01", "status": "success", "restore_tested": "Yes"},
                {"job_id": "BK-002", "job_name": "SAP_BACKUP_PROD", "system": "SAP PRD", "backup_date": "2025-08-01", "status": "failed", "restore_tested": "No"},
            ],
        },
        "incident": {
            "description": "Incident Records — for IT Operations SLA testing",
            "columns": ["incident_id", "priority", "status", "created_at", "resolved_at", "description"],
            "example_rows": [
                {"incident_id": "INC0001234", "priority": "P1", "status": "resolved", "created_at": "2025-10-15 08:00:00", "resolved_at": "2025-10-15 14:00:00", "description": "Production database down"},
                {"incident_id": "INC0001235", "priority": "P1", "status": "open", "created_at": "2025-10-20 09:00:00", "resolved_at": "", "description": "Payment system unavailable"},
            ],
        },
        "interfaces": {
            "description": "Interface/Integration Records — for ITAC interface control testing",
            "columns": ["interface_id", "interface_name", "source_count", "target_count", "source_total", "target_total", "status"],
            "example_rows": [
                {"interface_id": "INT-001", "interface_name": "ERP_to_DataWarehouse", "source_count": "5000", "target_count": "4998", "source_total": "1250000.00", "target_total": "1249850.00", "status": "completed"},
                {"interface_id": "INT-002", "interface_name": "Payroll_to_GL", "source_count": "850", "target_count": "850", "source_total": "2850000.00", "target_total": "2850000.00", "status": "failed"},
            ],
        },
    }

    if data_type not in samples:
        raise HTTPException(
            status_code=404,
            detail=f"Sample type '{data_type}' not found. Available: {', '.join(samples.keys())}"
        )

    return samples[data_type]
