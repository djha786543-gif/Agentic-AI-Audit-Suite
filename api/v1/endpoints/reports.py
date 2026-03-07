"""
api/v1/endpoints/reports.py
Phase 6 — Enterprise Reporting

Endpoints for:
  - Report definition management
  - On-demand report generation (executive summary, compliance status, KPI dashboard)
  - Report run history
  - Report schedule management
  - Executive dashboard aggregation
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import func, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from auth.context import AuthContext
from auth.rbac import UserRole, require_role
from db.async_session import get_async_db
from models.alerts import ComplianceAlert
from models.evaluation import ControlEvaluation, SODConflict
from models.exceptions import AuditException
from models.finding import Finding
from models.governance import ComplianceFramework, ComplianceMapping, RiskRegisterEntry
from models.reports import ReportDefinition, ReportRun, ReportSchedule
from schemas.reports import (
    ComplianceStatusSummary,
    ExecutiveDashboard,
    KPISummary,
    ReportDefinitionCreate,
    ReportDefinitionResponse,
    ReportRunRequest,
    ReportRunResponse,
    ReportScheduleCreate,
    ReportScheduleResponse,
)

router = APIRouter()

# ── Helpers ────────────────────────────────────────────────────────────────────

async def _build_kpis(db: AsyncSession) -> KPISummary:
    """Aggregate KPIs from live database state."""
    # Control evaluations
    ctrl_result = await db.execute(select(ControlEvaluation))
    evaluations = ctrl_result.scalars().all()
    total = len(evaluations)
    passed = sum(1 for e in evaluations if e.status == "passed")
    failed = sum(1 for e in evaluations if e.status == "failed")
    exception_count = sum(1 for e in evaluations if e.status == "exception")
    pass_rate = round((passed / total * 100), 1) if total > 0 else 0.0

    # Open exceptions
    exc_result = await db.execute(
        select(AuditException).filter(AuditException.state != "closed")
    )
    open_exceptions = len(exc_result.scalars().all())

    # Critical findings
    crit_result = await db.execute(
        select(Finding).filter(Finding.severity == "critical")
    )
    critical_findings = len(crit_result.scalars().all())

    # SOD conflicts (unresolved)
    sod_result = await db.execute(
        select(SODConflict).filter(SODConflict.resolved.is_(False))
    )
    sod_conflicts = len(sod_result.scalars().all())

    # Open alerts
    alert_result = await db.execute(
        select(ComplianceAlert).filter(ComplianceAlert.status == "open")
    )
    open_alerts = len(alert_result.scalars().all())

    # Overall risk rating
    if critical_findings > 0 or sod_conflicts > 5:
        overall = "CRITICAL"
    elif failed > 3 or open_exceptions > 10:
        overall = "HIGH"
    elif failed > 0 or open_exceptions > 0:
        overall = "MEDIUM"
    else:
        overall = "LOW"

    return KPISummary(
        total_controls_tested=total,
        controls_passed=passed,
        controls_failed=failed,
        controls_exception=exception_count,
        pass_rate_pct=pass_rate,
        open_exceptions=open_exceptions,
        critical_findings=critical_findings,
        sod_conflicts=sod_conflicts,
        open_alerts=open_alerts,
        overall_risk_rating=overall,
        generated_at=datetime.now(timezone.utc),
    )


async def _build_compliance_status(db: AsyncSession) -> List[ComplianceStatusSummary]:
    """Summarise coverage per compliance framework."""
    fw_result = await db.execute(
        select(ComplianceFramework).filter(ComplianceFramework.is_active.is_(True))
    )
    frameworks = fw_result.scalars().all()

    summaries: List[ComplianceStatusSummary] = []
    for fw in frameworks:
        mapping_result = await db.execute(
            select(ComplianceMapping).filter(ComplianceMapping.framework_id == fw.framework_id)
        )
        mappings = mapping_result.scalars().all()
        total_mapped = len(mappings)
        fully = sum(1 for m in mappings if m.mapping_status == "mapped")
        gaps = sum(1 for m in mappings if m.mapping_status == "gap")
        partial = sum(1 for m in mappings if m.mapping_status == "partial")
        coverage = round((fully / total_mapped * 100), 1) if total_mapped > 0 else 0.0
        summaries.append(
            ComplianceStatusSummary(
                framework_id=fw.framework_id,
                framework_name=fw.name,
                total_mapped=total_mapped,
                fully_mapped=fully,
                gaps=gaps,
                partial=partial,
                coverage_pct=coverage,
            )
        )
    return summaries


# ══════════════════════════════════════════════════════════════════════════════
# Executive Dashboard
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/dashboard", response_model=ExecutiveDashboard)
async def executive_dashboard(
    db: AsyncSession = Depends(get_async_db),
) -> ExecutiveDashboard:
    """
    Real-time executive dashboard aggregating KPIs, compliance coverage,
    recent critical alerts, and top risks.
    """
    kpis = await _build_kpis(db)
    compliance = await _build_compliance_status(db)

    # Recent open/acknowledged alerts (max 5)
    alert_result = await db.execute(
        select(ComplianceAlert)
        .filter(ComplianceAlert.status.in_(["open", "acknowledged"]))
        .order_by(desc(ComplianceAlert.created_at))
        .limit(5)
    )
    recent_alerts: List[Dict[str, Any]] = [
        {
            "id": str(a.id),
            "title": a.title,
            "severity": a.severity,
            "status": a.status,
            "created_at": a.created_at.isoformat(),
        }
        for a in alert_result.scalars().all()
    ]

    # Top risks by score (max 5)
    risk_result = await db.execute(
        select(RiskRegisterEntry)
        .filter(RiskRegisterEntry.status != "closed")
        .order_by(desc(RiskRegisterEntry.risk_score))
        .limit(5)
    )
    top_risks: List[Dict[str, Any]] = [
        {
            "risk_id": r.risk_id,
            "title": r.title,
            "risk_score": r.risk_score,
            "risk_rating": r.risk_rating,
            "status": r.status,
            "owner": r.owner,
        }
        for r in risk_result.scalars().all()
    ]

    return ExecutiveDashboard(
        kpis=kpis,
        compliance_status=compliance,
        recent_alerts=recent_alerts,
        top_risks=top_risks,
        generated_at=datetime.now(timezone.utc),
    )


# ══════════════════════════════════════════════════════════════════════════════
# KPI Summary (standalone)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/kpis", response_model=KPISummary)
async def kpi_summary(
    db: AsyncSession = Depends(get_async_db),
) -> KPISummary:
    """Standalone KPI snapshot for embedding in other dashboards."""
    return await _build_kpis(db)


# ══════════════════════════════════════════════════════════════════════════════
# Report Definitions
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/definitions", response_model=List[ReportDefinitionResponse])
async def list_report_definitions(
    db: AsyncSession = Depends(get_async_db),
) -> List[ReportDefinitionResponse]:
    result = await db.execute(
        select(ReportDefinition).order_by(desc(ReportDefinition.created_at))
    )
    return result.scalars().all()


@router.post("/definitions", response_model=ReportDefinitionResponse, status_code=201)
async def create_report_definition(
    defn_in: ReportDefinitionCreate,
    db: AsyncSession = Depends(get_async_db),
    ctx: AuthContext = Depends(require_role(UserRole.INTERNAL_AUDITOR)),
) -> ReportDefinitionResponse:
    record = ReportDefinition(
        org_id=ctx.org_id,
        created_by=ctx.username,
        **defn_in.model_dump(),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


# ══════════════════════════════════════════════════════════════════════════════
# Report Runs (on-demand generation)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/runs", response_model=List[ReportRunResponse])
async def list_report_runs(
    limit: int = 50,
    db: AsyncSession = Depends(get_async_db),
) -> List[ReportRunResponse]:
    result = await db.execute(
        select(ReportRun).order_by(desc(ReportRun.created_at)).limit(limit)
    )
    return result.scalars().all()


@router.post("/runs", response_model=ReportRunResponse, status_code=201)
async def generate_report(
    req: ReportRunRequest,
    db: AsyncSession = Depends(get_async_db),
    ctx: AuthContext = Depends(require_role(UserRole.INTERNAL_AUDITOR)),
) -> ReportRunResponse:
    """
    Trigger an on-demand report.  The result_payload is generated synchronously
    for the supported built-in report types; custom types store an empty payload
    until a background worker fills them in.
    """
    now = datetime.now(timezone.utc)
    run = ReportRun(
        org_id=ctx.org_id,
        report_definition_id=req.report_definition_id,
        report_type=req.report_type,
        name=req.name,
        parameters=req.parameters,
        generated_by=ctx.username,
        started_at=now,
        status="running",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # ── Generate payload for built-in types ──────────────────────────────────
    payload: Dict[str, Any] = {}
    error_msg: str | None = None
    try:
        if req.report_type == "executive_summary":
            kpis = await _build_kpis(db)
            compliance = await _build_compliance_status(db)
            payload = {
                "report_type": "executive_summary",
                "kpis": kpis.model_dump(mode="json"),
                "compliance_status": [c.model_dump() for c in compliance],
                "standard_refs": [
                    "COSO 2013 Internal Control Framework",
                    "SOX Section 302 & 404",
                    "PCAOB AS 2201",
                    "ISO 27001:2022",
                    "COBIT 2019",
                ],
            }

        elif req.report_type == "compliance_status":
            compliance = await _build_compliance_status(db)
            payload = {
                "report_type": "compliance_status",
                "frameworks": [c.model_dump() for c in compliance],
            }

        elif req.report_type == "kpi_dashboard":
            kpis = await _build_kpis(db)
            payload = {"report_type": "kpi_dashboard", "kpis": kpis.model_dump(mode="json")}

        elif req.report_type == "audit_findings":
            finding_result = await db.execute(
                select(Finding).order_by(desc(Finding.created_at)).limit(200)
            )
            findings = finding_result.scalars().all()
            payload = {
                "report_type": "audit_findings",
                "total": len(findings),
                "findings": [
                    {
                        "id": str(f.id),
                        "control_id": f.control_id,
                        "severity": f.severity,
                        "status": f.status,
                        "description": f.description,
                        "logic_breakdown": f.logic_breakdown,
                        "remediation_owner": f.remediation_owner,
                        "remediation_due_date": f.remediation_due_date.isoformat() if f.remediation_due_date else None,
                        "created_at": f.created_at.isoformat() if f.created_at else None,
                    }
                    for f in findings
                ],
            }

        elif req.report_type == "sod_matrix":
            sod_result = await db.execute(
                select(SODConflict).order_by(desc(SODConflict.detected_at)).limit(200)
            )
            conflicts = sod_result.scalars().all()
            payload = {
                "report_type": "sod_matrix",
                "total_conflicts": len(conflicts),
                "unresolved": sum(1 for c in conflicts if not c.resolved),
                "conflicts": [
                    {
                        "id": str(c.id),
                        "user_id": c.user_id,
                        "role_a": c.role_a,
                        "role_b": c.role_b,
                        "conflict_type": c.conflict_type,
                        "risk_level": c.risk_level,
                        "resolved": c.resolved,
                    }
                    for c in conflicts
                ],
            }

        elif req.report_type == "risk_register":
            risk_result = await db.execute(
                select(RiskRegisterEntry).order_by(desc(RiskRegisterEntry.risk_score))
            )
            risks = risk_result.scalars().all()
            payload = {
                "report_type": "risk_register",
                "total_risks": len(risks),
                "risks": [
                    {
                        "risk_id": r.risk_id,
                        "title": r.title,
                        "category": r.category,
                        "risk_score": r.risk_score,
                        "risk_rating": r.risk_rating,
                        "status": r.status,
                        "treatment": r.treatment,
                        "owner": r.owner,
                    }
                    for r in risks
                ],
            }

        elif req.report_type == "continuous_assurance":
            kpis = await _build_kpis(db)
            alert_result = await db.execute(
                select(ComplianceAlert).order_by(desc(ComplianceAlert.created_at)).limit(50)
            )
            alerts = alert_result.scalars().all()
            payload = {
                "report_type": "continuous_assurance",
                "kpis": kpis.model_dump(mode="json"),
                "alerts": [
                    {
                        "id": str(a.id),
                        "title": a.title,
                        "severity": a.severity,
                        "status": a.status,
                        "created_at": a.created_at.isoformat(),
                    }
                    for a in alerts
                ],
            }

        else:
            payload = {
                "report_type": req.report_type,
                "message": "Custom report type — payload generated by background worker.",
            }

        run.status = "complete"
        run.result_payload = payload
        run.completed_at = datetime.now(timezone.utc)

    except Exception as exc:
        logger.exception("report generation failed: report_type=%s name=%s", req.report_type, req.name)
        run.status = "failed"
        run.error_message = str(exc)
        error_msg = str(exc)

    await db.commit()
    await db.refresh(run)
    return run


@router.get("/external/review-package")
async def external_review_package(
    db: AsyncSession = Depends(get_async_db),
    _: AuthContext = Depends(require_role(UserRole.EXTERNAL_AUDITOR, UserRole.INTERNAL_AUDITOR)),
) -> Dict[str, Any]:
    """Read-only package for external auditors to review evidence and conclusions."""
    finding_result = await db.execute(select(Finding).order_by(desc(Finding.created_at)).limit(200))
    findings = finding_result.scalars().all()
    return {
        "mode": "read_only",
        "package_generated_at": datetime.now(timezone.utc).isoformat(),
        "findings": [
            {
                "id": str(f.id),
                "control_id": f.control_id,
                "severity": f.severity,
                "status": f.status,
                "description": f.description,
                "remediation_owner": f.remediation_owner,
                "remediation_due_date": f.remediation_due_date.isoformat() if f.remediation_due_date else None,
                "logic_breakdown": f.logic_breakdown,
            }
            for f in findings
        ],
    }


@router.get("/exports/workpaper")
async def export_workpaper(
    target: str = "workiva",
    db: AsyncSession = Depends(get_async_db),
    _: AuthContext = Depends(require_role(UserRole.INTERNAL_AUDITOR, UserRole.EXTERNAL_AUDITOR)),
):
    """One-click export payloads for audit management tools."""
    finding_result = await db.execute(select(Finding).order_by(desc(Finding.created_at)).limit(1000))
    findings = finding_result.scalars().all()
    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "target": target,
        "findings": [
            {
                "finding_id": str(f.id),
                "control_id": f.control_id,
                "severity": f.severity,
                "status": f.status,
                "description": f.description,
                "remediation_owner": f.remediation_owner,
                "remediation_due_date": f.remediation_due_date.isoformat() if f.remediation_due_date else None,
            }
            for f in findings
        ],
    }

    target_normalized = target.strip().lower()
    if target_normalized in {"workiva", "teammate", "servicenow", "json"}:
        return payload

    if target_normalized == "xml":
        root = ET.Element("workpaperExport", attrib={"target": "generic_xml"})
        ET.SubElement(root, "exportedAt").text = payload["exported_at"]
        findings_node = ET.SubElement(root, "findings")
        for f in payload["findings"]:
            node = ET.SubElement(findings_node, "finding")
            for k, v in f.items():
                ET.SubElement(node, k).text = "" if v is None else str(v)
        xml_bytes = ET.tostring(root, encoding="utf-8")
        return Response(content=xml_bytes, media_type="application/xml")

    raise HTTPException(status_code=400, detail="Unsupported export target. Use workiva, teammate, servicenow, json, or xml.")


@router.get("/runs/{run_id}", response_model=ReportRunResponse)
async def get_report_run(
    run_id: str,
    db: AsyncSession = Depends(get_async_db),
) -> ReportRunResponse:
    result = await db.execute(
        select(ReportRun).filter(ReportRun.id == run_id)
    )
    record = result.scalars().first()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report run not found")
    return record


# ══════════════════════════════════════════════════════════════════════════════
# Report Schedules
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/schedules", response_model=List[ReportScheduleResponse])
async def list_schedules(
    db: AsyncSession = Depends(get_async_db),
) -> List[ReportScheduleResponse]:
    result = await db.execute(
        select(ReportSchedule).order_by(ReportSchedule.created_at)
    )
    return result.scalars().all()


@router.post("/schedules", response_model=ReportScheduleResponse, status_code=201)
async def create_schedule(
    sched_in: ReportScheduleCreate,
    db: AsyncSession = Depends(get_async_db),
    ctx: AuthContext = Depends(require_role(UserRole.INTERNAL_AUDITOR)),
) -> ReportScheduleResponse:
    record = ReportSchedule(
        org_id=ctx.org_id,
        created_by=ctx.username,
        **sched_in.model_dump(),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record
