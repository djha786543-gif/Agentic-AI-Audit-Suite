"""
api/v1/endpoints/governance.py
Phase 5 — Continuous Assurance & Governance Layer

Endpoints for:
  - Governance policies
  - Compliance frameworks
  - Compliance mappings (control ↔ framework requirement)
  - Risk register
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from auth.context import AuthContext
from auth.rbac import UserRole, require_role
from db.async_session import get_async_db
from models.governance import (
    ComplianceFramework,
    ComplianceMapping,
    GovernancePolicy,
    RiskRegisterEntry,
)
from schemas.governance import (
    ComplianceFrameworkCreate,
    ComplianceFrameworkResponse,
    ComplianceMappingCreate,
    ComplianceMappingResponse,
    GovernancePolicyCreate,
    GovernancePolicyResponse,
    RiskRegisterCreate,
    RiskRegisterResponse,
)

router = APIRouter()

_RISK_RATING_MAP = {
    (1, 1): "LOW", (1, 2): "LOW",  (1, 3): "LOW",  (1, 4): "MEDIUM", (1, 5): "MEDIUM",
    (2, 1): "LOW", (2, 2): "LOW",  (2, 3): "MEDIUM",(2, 4): "MEDIUM", (2, 5): "HIGH",
    (3, 1): "LOW", (3, 2): "MEDIUM",(3,3): "MEDIUM",(3, 4): "HIGH",  (3, 5): "HIGH",
    (4, 1): "MEDIUM",(4,2): "MEDIUM",(4,3): "HIGH", (4, 4): "HIGH",  (4, 5): "CRITICAL",
    (5, 1): "MEDIUM",(5,2): "HIGH", (5,3): "HIGH",  (5, 4): "CRITICAL",(5,5): "CRITICAL",
}


def _compute_risk(likelihood: int, impact: int):
    score = round(likelihood * impact, 1)
    rating = _RISK_RATING_MAP.get((likelihood, impact), "MEDIUM")
    return score, rating


# ══════════════════════════════════════════════════════════════════════════════
# Governance Policies
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/policies", response_model=List[GovernancePolicyResponse])
async def list_policies(
    limit: int = 50,
    db: AsyncSession = Depends(get_async_db),
) -> List[GovernancePolicyResponse]:
    result = await db.execute(
        select(GovernancePolicy)
        .order_by(desc(GovernancePolicy.created_at))
        .limit(limit)
    )
    return result.scalars().all()


@router.post("/policies", response_model=GovernancePolicyResponse, status_code=201)
async def create_policy(
    policy_in: GovernancePolicyCreate,
    db: AsyncSession = Depends(get_async_db),
    ctx: AuthContext = Depends(require_role(UserRole.INTERNAL_AUDITOR)),
) -> GovernancePolicyResponse:
    record = GovernancePolicy(
        org_id=ctx.org_id,
        **policy_in.model_dump(),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


@router.get("/policies/{policy_id}", response_model=GovernancePolicyResponse)
async def get_policy(
    policy_id: str,
    db: AsyncSession = Depends(get_async_db),
) -> GovernancePolicyResponse:
    result = await db.execute(
        select(GovernancePolicy).filter(GovernancePolicy.policy_id == policy_id)
    )
    record = result.scalars().first()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")
    return record


# ══════════════════════════════════════════════════════════════════════════════
# Compliance Frameworks
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/frameworks", response_model=List[ComplianceFrameworkResponse])
async def list_frameworks(
    db: AsyncSession = Depends(get_async_db),
) -> List[ComplianceFrameworkResponse]:
    result = await db.execute(
        select(ComplianceFramework).order_by(ComplianceFramework.framework_id)
    )
    return result.scalars().all()


@router.post("/frameworks", response_model=ComplianceFrameworkResponse, status_code=201)
async def create_framework(
    fw_in: ComplianceFrameworkCreate,
    db: AsyncSession = Depends(get_async_db),
    ctx: AuthContext = Depends(require_role(UserRole.INTERNAL_AUDITOR)),
) -> ComplianceFrameworkResponse:
    record = ComplianceFramework(org_id=ctx.org_id, **fw_in.model_dump())
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


# ══════════════════════════════════════════════════════════════════════════════
# Compliance Mappings
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/mappings", response_model=List[ComplianceMappingResponse])
async def list_mappings(
    framework_id: str | None = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db),
) -> List[ComplianceMappingResponse]:
    q = select(ComplianceMapping).order_by(ComplianceMapping.framework_id)
    if framework_id:
        q = q.filter(ComplianceMapping.framework_id == framework_id)
    result = await db.execute(q.limit(limit))
    return result.scalars().all()


@router.post("/mappings", response_model=ComplianceMappingResponse, status_code=201)
async def create_mapping(
    mapping_in: ComplianceMappingCreate,
    db: AsyncSession = Depends(get_async_db),
    ctx: AuthContext = Depends(require_role(UserRole.INTERNAL_AUDITOR)),
) -> ComplianceMappingResponse:
    record = ComplianceMapping(org_id=ctx.org_id, **mapping_in.model_dump())
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


# ══════════════════════════════════════════════════════════════════════════════
# Risk Register
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/risks", response_model=List[RiskRegisterResponse])
async def list_risks(
    status: str | None = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db),
) -> List[RiskRegisterResponse]:
    q = select(RiskRegisterEntry).order_by(desc(RiskRegisterEntry.risk_score))
    if status:
        q = q.filter(RiskRegisterEntry.status == status)
    result = await db.execute(q.limit(limit))
    return result.scalars().all()


@router.post("/risks", response_model=RiskRegisterResponse, status_code=201)
async def create_risk(
    risk_in: RiskRegisterCreate,
    db: AsyncSession = Depends(get_async_db),
    ctx: AuthContext = Depends(require_role(UserRole.INTERNAL_AUDITOR)),
) -> RiskRegisterResponse:
    data = risk_in.model_dump()
    score, rating = _compute_risk(data["inherent_likelihood"], data["inherent_impact"])
    # Compute residual score if provided
    if data.get("residual_likelihood") and data.get("residual_impact"):
        residual_score, rating = _compute_risk(
            data["residual_likelihood"], data["residual_impact"]
        )
        score = residual_score
    record = RiskRegisterEntry(org_id=ctx.org_id, risk_score=score, risk_rating=rating, **data)
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


@router.get("/risks/{risk_id}", response_model=RiskRegisterResponse)
async def get_risk(
    risk_id: str,
    db: AsyncSession = Depends(get_async_db),
) -> RiskRegisterResponse:
    result = await db.execute(
        select(RiskRegisterEntry).filter(RiskRegisterEntry.risk_id == risk_id)
    )
    record = result.scalars().first()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk not found")
    return record
