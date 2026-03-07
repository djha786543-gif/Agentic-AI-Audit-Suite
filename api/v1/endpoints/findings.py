"""Findings workflow endpoints for remediation, peer re-performance, and management responses."""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.context import AuthContext
from auth.rbac import UserRole, require_role
from core.config import settings
from db.async_session import get_async_db
from models.finding import Finding, ManagementResponse
from models.governance import GovernanceAuditLog
from models.system_logs import WorkflowLog
from schemas.finding import (
    FindingResponse,
    ManagementResponseCreate,
    ManagementResponseResponse,
    RemediationAssignment,
)

router = APIRouter()


def _to_naive_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


async def _append_worm_log(
    db: AsyncSession,
    *,
    org_id: str,
    actor: str,
    event_type: str,
    event_payload: Dict[str, Any],
) -> None:
    prev_result = await db.execute(
        select(GovernanceAuditLog).order_by(desc(GovernanceAuditLog.created_at)).limit(1)
    )
    prev = prev_result.scalars().first()
    prev_hash = prev.entry_hash if prev else "GENESIS"

    body = {
        "org_id": org_id,
        "actor": actor,
        "event_type": event_type,
        "event_payload": event_payload,
        "previous_hash": prev_hash,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    serialized = json.dumps(body, sort_keys=True, separators=(",", ":"))
    entry_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    signature = hmac.new(settings.SECRET_KEY.encode("utf-8"), entry_hash.encode("utf-8"), hashlib.sha256).hexdigest()

    db.add(
        GovernanceAuditLog(
            org_id=org_id,
            actor=actor,
            event_type=event_type,
            event_payload=event_payload,
            previous_hash=prev_hash,
            entry_hash=entry_hash,
            signature=signature,
            immutable=True,
        )
    )


@router.get("/", response_model=List[FindingResponse])
async def list_findings(
    limit: int = 200,
    db: AsyncSession = Depends(get_async_db),
    _: AuthContext = Depends(require_role(UserRole.INTERNAL_AUDITOR, UserRole.EXTERNAL_AUDITOR, UserRole.PROCESS_OWNER)),
) -> List[FindingResponse]:
    result = await db.execute(select(Finding).order_by(desc(Finding.created_at)).limit(limit))
    return result.scalars().all()


@router.patch("/{finding_id}/remediation", response_model=FindingResponse)
async def assign_remediation(
    finding_id: uuid.UUID,
    body: RemediationAssignment,
    db: AsyncSession = Depends(get_async_db),
    ctx: AuthContext = Depends(require_role(UserRole.INTERNAL_AUDITOR)),
) -> FindingResponse:
    result = await db.execute(select(Finding).filter(Finding.id == finding_id))
    finding = result.scalars().first()
    if finding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found")

    finding.remediation_owner = body.remediation_owner
    finding.remediation_due_date = _to_naive_utc(body.remediation_due_date)
    finding.status = "management_response"

    await _append_worm_log(
        db,
        org_id=ctx.org_id,
        actor=ctx.username,
        event_type="REMEDIATION_ASSIGNED",
        event_payload={
            "finding_id": str(finding.id),
            "owner": body.remediation_owner,
            "due_date": body.remediation_due_date.isoformat(),
        },
    )

    if hasattr(db, "add"):
        db.add(
            WorkflowLog(
                org_id=ctx.org_id,
                user=ctx.username,
                action="workflow_approval",
                workflow_name="finding_remediation_assignment",
                resource=str(finding.id),
                stage_from="open",
                stage_to="management_response",
                approval_required=True,
                approved=True,
                metadata_json={
                    "remediation_owner": body.remediation_owner,
                    "remediation_due_date": body.remediation_due_date.isoformat(),
                },
            )
        )

    await db.commit()
    await db.refresh(finding)
    return finding


@router.post("/{finding_id}/management-response", response_model=ManagementResponseResponse, status_code=201)
async def submit_management_response(
    finding_id: uuid.UUID,
    body: ManagementResponseCreate,
    db: AsyncSession = Depends(get_async_db),
    ctx: AuthContext = Depends(require_role(UserRole.INTERNAL_AUDITOR, UserRole.PROCESS_OWNER)),
) -> ManagementResponseResponse:
    f_result = await db.execute(select(Finding).filter(Finding.id == finding_id))
    finding = f_result.scalars().first()
    if finding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found")

    record = ManagementResponse(
        org_id=ctx.org_id,
        finding_id=finding_id,
        response_text=body.response_text,
        responsible_owner=body.responsible_owner,
        target_date=_to_naive_utc(body.target_date),
    )
    db.add(record)
    finding.status = "remediation"

    await _append_worm_log(
        db,
        org_id=ctx.org_id,
        actor=ctx.username,
        event_type="MANAGEMENT_RESPONSE_SUBMITTED",
        event_payload={
            "finding_id": str(finding_id),
            "owner": body.responsible_owner,
            "target_date": body.target_date.isoformat() if body.target_date else None,
        },
    )

    if hasattr(db, "add"):
        db.add(
            WorkflowLog(
                org_id=ctx.org_id,
                user=ctx.username,
                action="workflow_approval",
                workflow_name="finding_management_response",
                resource=str(finding_id),
                stage_from="management_response",
                stage_to="remediation",
                approval_required=True,
                approved=True,
                metadata_json={
                    "responsible_owner": body.responsible_owner,
                    "target_date": body.target_date.isoformat() if body.target_date else None,
                },
            )
        )

    await db.commit()
    await db.refresh(record)
    return record


@router.get("/{finding_id}/reperformance")
async def reperformance_payload(
    finding_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
    _: AuthContext = Depends(require_role(UserRole.INTERNAL_AUDITOR, UserRole.EXTERNAL_AUDITOR)),
) -> dict:
    result = await db.execute(select(Finding).filter(Finding.id == finding_id))
    finding = result.scalars().first()
    if finding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found")
    return {
        "finding_id": str(finding.id),
        "logic_breakdown": finding.logic_breakdown,
        "reperformance": finding.reperformance_payload,
    }


@router.delete("/{finding_id}")
async def delete_finding_blocked(
    finding_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db),
    ctx: AuthContext = Depends(require_role(UserRole.INTERNAL_AUDITOR)),
) -> dict:
    """
    WORM behavior: findings are not physically deleted.
    Any delete attempt is logged as potential tampering.
    """
    await _append_worm_log(
        db,
        org_id=ctx.org_id,
        actor=ctx.username,
        event_type="LOG_TAMPERING_ALERT",
        event_payload={
            "finding_id": str(finding_id),
            "action": "DELETE_ATTEMPT_BLOCKED",
            "message": "Write-once policy prevented deletion.",
        },
    )

    if hasattr(db, "add"):
        db.add(
            WorkflowLog(
                org_id=ctx.org_id,
                user=ctx.username,
                action="workflow_approval",
                workflow_name="finding_worm_guard",
                resource=str(finding_id),
                stage_from="delete_requested",
                stage_to="delete_blocked",
                approval_required=False,
                approved=False,
                metadata_json={"policy": "WORM"},
            )
        )
    await db.commit()
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Delete blocked by WORM policy. Log tampering alert recorded.",
    )
