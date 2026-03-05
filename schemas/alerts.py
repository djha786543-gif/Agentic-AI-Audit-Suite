"""
schemas/alerts.py
Phase 5 — Continuous Assurance & Governance Layer

Pydantic request/response shapes for alert rules and compliance alerts.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional
import uuid

from pydantic import BaseModel, ConfigDict


# ── Alert Rule ─────────────────────────────────────────────────────────────────

class AlertRuleCreate(BaseModel):
    rule_id: str
    name: str
    description: Optional[str] = None
    metric: str
    operator: str = "gte"
    threshold: int = 1
    severity: str = "HIGH"
    is_active: bool = True


class AlertRuleResponse(BaseModel):
    id: uuid.UUID
    org_id: str
    rule_id: str
    name: str
    description: Optional[str] = None
    metric: str
    operator: str
    threshold: int
    severity: str
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ── Compliance Alert ───────────────────────────────────────────────────────────

class ComplianceAlertCreate(BaseModel):
    title: str
    description: Optional[str] = None
    severity: str = "HIGH"
    alert_rule_id: Optional[uuid.UUID] = None
    metric_value: Optional[int] = None
    affected_controls: Optional[List[str]] = None


class AlertAcknowledge(BaseModel):
    comment: str = ""


class AlertResolve(BaseModel):
    comment: str = ""


class ComplianceAlertResponse(BaseModel):
    id: uuid.UUID
    org_id: str
    alert_rule_id: Optional[uuid.UUID] = None
    title: str
    description: Optional[str] = None
    severity: str
    status: str
    metric_value: Optional[int] = None
    affected_controls: Optional[List[str]] = None
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
