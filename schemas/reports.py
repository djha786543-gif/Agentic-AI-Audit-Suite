"""
schemas/reports.py
Phase 6 — Enterprise Reporting

Pydantic shapes for report definitions, runs, schedules, and the
executive/compliance dashboard aggregates.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict


# ── Report Definition ──────────────────────────────────────────────────────────

class ReportDefinitionCreate(BaseModel):
    report_type: str
    name: str
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    is_active: bool = True


class ReportDefinitionResponse(BaseModel):
    id: uuid.UUID
    org_id: str
    report_type: str
    name: str
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    is_active: bool
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ── Report Run ─────────────────────────────────────────────────────────────────

class ReportRunRequest(BaseModel):
    """Trigger an on-demand report run."""
    report_type: str
    name: str
    parameters: Optional[Dict[str, Any]] = None
    report_definition_id: Optional[uuid.UUID] = None


class ReportRunResponse(BaseModel):
    id: uuid.UUID
    org_id: str
    report_definition_id: Optional[uuid.UUID] = None
    report_type: str
    name: str
    status: str
    parameters: Optional[Dict[str, Any]] = None
    result_payload: Optional[Dict[str, Any]] = None
    generated_by: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ── Report Schedule ────────────────────────────────────────────────────────────

class ReportScheduleCreate(BaseModel):
    report_definition_id: uuid.UUID
    cron_expression: str = "0 8 * * 1"
    is_active: bool = True


class ReportScheduleResponse(BaseModel):
    id: uuid.UUID
    org_id: str
    report_definition_id: uuid.UUID
    cron_expression: str
    is_active: bool
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    created_by: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ── Dashboard Aggregates ───────────────────────────────────────────────────────

class KPISummary(BaseModel):
    total_controls_tested: int
    controls_passed: int
    controls_failed: int
    controls_exception: int
    pass_rate_pct: float
    open_exceptions: int
    critical_findings: int
    sod_conflicts: int
    open_alerts: int
    overall_risk_rating: str
    generated_at: datetime


class ComplianceStatusSummary(BaseModel):
    framework_id: str
    framework_name: str
    total_mapped: int
    fully_mapped: int
    gaps: int
    partial: int
    coverage_pct: float


class ExecutiveDashboard(BaseModel):
    kpis: KPISummary
    compliance_status: List[ComplianceStatusSummary]
    recent_alerts: List[Dict[str, Any]]
    top_risks: List[Dict[str, Any]]
    generated_at: datetime
