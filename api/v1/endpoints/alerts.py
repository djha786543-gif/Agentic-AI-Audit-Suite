"""
api/v1/endpoints/alerts.py
Phase 5 — Continuous Assurance & Governance Layer

Endpoints for alert rule management and compliance alert lifecycle.
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
from models.alerts import AlertRule, ComplianceAlert
from schemas.alerts import (
    AlertAcknowledge,
    AlertResolve,
    AlertRuleCreate,
    AlertRuleResponse,
    ComplianceAlertCreate,
    ComplianceAlertResponse,
)

router = APIRouter()


# ══════════════════════════════════════════════════════════════════════════════
# Alert Rules
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/rules", response_model=List[AlertRuleResponse])
async def list_alert_rules(
    db: AsyncSession = Depends(get_async_db),
) -> List[AlertRuleResponse]:
    result = await db.execute(
        select(AlertRule).order_by(AlertRule.rule_id)
    )
    return result.scalars().all()


@router.post("/rules", response_model=AlertRuleResponse, status_code=201)
async def create_alert_rule(
    rule_in: AlertRuleCreate,
    db: AsyncSession = Depends(get_async_db),
    ctx: AuthContext = Depends(require_role(UserRole.INTERNAL_AUDITOR)),
) -> AlertRuleResponse:
    record = AlertRule(org_id=ctx.org_id, **rule_in.model_dump())
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


# ══════════════════════════════════════════════════════════════════════════════
# Compliance Alerts
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/", response_model=List[ComplianceAlertResponse])
async def list_alerts(
    alert_status: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_async_db),
) -> List[ComplianceAlertResponse]:
    q = select(ComplianceAlert).order_by(desc(ComplianceAlert.created_at))
    if alert_status:
        q = q.filter(ComplianceAlert.status == alert_status)
    result = await db.execute(q.limit(limit))
    return result.scalars().all()


@router.post("/", response_model=ComplianceAlertResponse, status_code=201)
async def create_alert(
    alert_in: ComplianceAlertCreate,
    db: AsyncSession = Depends(get_async_db),
    ctx: AuthContext = Depends(require_role(UserRole.INTERNAL_AUDITOR, UserRole.CONNECTOR_SERVICE)),
) -> ComplianceAlertResponse:
    record = ComplianceAlert(org_id=ctx.org_id, **alert_in.model_dump())
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


@router.patch("/{alert_id}/acknowledge", response_model=ComplianceAlertResponse)
async def acknowledge_alert(
    alert_id: str,
    body: AlertAcknowledge,
    db: AsyncSession = Depends(get_async_db),
    ctx: AuthContext = Depends(require_role(UserRole.INTERNAL_AUDITOR)),
) -> ComplianceAlertResponse:
    result = await db.execute(
        select(ComplianceAlert).filter(ComplianceAlert.id == alert_id)
    )
    record = result.scalars().first()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    if record.status != "open":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Alert is already '{record.status}', cannot acknowledge.",
        )
    record.status = "acknowledged"
    record.acknowledged_by = ctx.username
    record.acknowledged_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(record)
    return record


@router.patch("/{alert_id}/resolve", response_model=ComplianceAlertResponse)
async def resolve_alert(
    alert_id: str,
    body: AlertResolve,
    db: AsyncSession = Depends(get_async_db),
    ctx: AuthContext = Depends(require_role(UserRole.INTERNAL_AUDITOR)),
) -> ComplianceAlertResponse:
    result = await db.execute(
        select(ComplianceAlert).filter(ComplianceAlert.id == alert_id)
    )
    record = result.scalars().first()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    if record.status == "resolved":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Alert is already resolved.",
        )
    record.status = "resolved"
    record.resolved_by = ctx.username
    record.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(record)
    return record
