"""
schemas/governance.py
Phase 5 — Continuous Assurance & Governance Layer

Pydantic request/response shapes for policies, frameworks,
compliance mappings, and the risk register.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


# ── Governance Policy ──────────────────────────────────────────────────────────

class GovernancePolicyCreate(BaseModel):
    policy_id: str
    title: str
    description: Optional[str] = None
    owner: Optional[str] = None
    effective_date: Optional[datetime] = None
    review_date: Optional[datetime] = None
    status: str = "active"
    version: str = "1.0"
    framework_refs: Optional[List[str]] = None


class GovernancePolicyResponse(BaseModel):
    id: uuid.UUID
    org_id: str
    policy_id: str
    title: str
    description: Optional[str] = None
    owner: Optional[str] = None
    effective_date: Optional[datetime] = None
    review_date: Optional[datetime] = None
    status: str
    version: str
    framework_refs: Optional[List[str]] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ── Compliance Framework ───────────────────────────────────────────────────────

class ComplianceFrameworkCreate(BaseModel):
    framework_id: str
    name: str
    version: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True


class ComplianceFrameworkResponse(BaseModel):
    id: uuid.UUID
    org_id: str
    framework_id: str
    name: str
    version: Optional[str] = None
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ── Compliance Mapping ─────────────────────────────────────────────────────────

class ComplianceMappingCreate(BaseModel):
    framework_id: str
    requirement_ref: str
    control_id: str
    mapping_status: str = "mapped"
    notes: Optional[str] = None
    last_assessed: Optional[datetime] = None


class ComplianceMappingResponse(BaseModel):
    id: uuid.UUID
    org_id: str
    framework_id: str
    requirement_ref: str
    control_id: str
    mapping_status: str
    notes: Optional[str] = None
    last_assessed: Optional[datetime] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ── Risk Register ──────────────────────────────────────────────────────────────

class RiskRegisterCreate(BaseModel):
    risk_id: str
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    inherent_likelihood: int = Field(default=3, ge=1, le=5)
    inherent_impact: int = Field(default=3, ge=1, le=5)
    residual_likelihood: Optional[int] = Field(default=None, ge=1, le=5)
    residual_impact: Optional[int] = Field(default=None, ge=1, le=5)
    owner: Optional[str] = None
    treatment: Optional[str] = None
    status: str = "open"
    related_controls: Optional[List[str]] = None


class RiskRegisterResponse(BaseModel):
    id: uuid.UUID
    org_id: str
    risk_id: str
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    inherent_likelihood: int
    inherent_impact: int
    residual_likelihood: Optional[int] = None
    residual_impact: Optional[int] = None
    risk_score: Optional[float] = None
    risk_rating: Optional[str] = None
    owner: Optional[str] = None
    treatment: Optional[str] = None
    status: str
    related_controls: Optional[List[str]] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
