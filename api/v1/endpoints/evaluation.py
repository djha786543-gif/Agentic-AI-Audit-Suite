"""
api/v1/endpoints/evaluation.py
───────────────────────────────
Control evaluation, SOD conflict, and audit exception endpoints.

Exception lifecycle: open → acknowledged → remediation_in_progress
                     → remediated → closed
                          ↘ accepted_risk → closed
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List
import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from auth.context import AuthContext, get_auth_context
from auth.rbac import UserRole, require_role
from db.async_session import get_async_db
from models.evaluation import ControlEvaluation, SODConflict
from models.exceptions import AuditException
from models.system_logs import WorkflowLog
from schemas.evaluation import (
    AuditExceptionCreate,
    AuditExceptionResponse,
    ControlEvaluationCreate,
    ControlEvaluationResponse,
    SODConflictCreate,
    SODConflictResponse,
)

router = APIRouter()

# ── Valid exception state transitions ─────────────────────────────────────────
_VALID_TRANSITIONS: Dict[str, List[str]] = {
    "open": ["acknowledged", "accepted_risk"],
    "acknowledged": ["remediation_in_progress", "accepted_risk"],
    "remediation_in_progress": ["remediated"],
    "remediated": ["closed"],
    "accepted_risk": ["closed"],
    "closed": [],
}

# DB schema in some deployed environments keeps `audit_exceptions.state` as VARCHAR(20).
# Persist a compact token while preserving canonical API state names.
_CANONICAL_TO_STORAGE: Dict[str, str] = {
    "remediation_in_progress": "remediation_progress",
}
_STORAGE_TO_CANONICAL: Dict[str, str] = {v: k for k, v in _CANONICAL_TO_STORAGE.items()}


def _to_storage_state(state: str) -> str:
    return _CANONICAL_TO_STORAGE.get(state, state)


def _to_canonical_state(state: str) -> str:
    return _STORAGE_TO_CANONICAL.get(state, state)


class ExceptionTransition(BaseModel):
    new_state: str
    comment: str = ""


# ── Control evaluations ───────────────────────────────────────────────────────

@router.get("/controls", response_model=List[ControlEvaluationResponse])
async def list_controls(
    limit: int = 50,
    db: AsyncSession = Depends(get_async_db),
) -> List[ControlEvaluationResponse]:
    result = await db.execute(
        select(ControlEvaluation)
        .order_by(desc(ControlEvaluation.evaluated_at))
        .limit(limit)
    )
    return result.scalars().all()


@router.post("/controls", response_model=ControlEvaluationResponse, status_code=201)
async def create_control_evaluation(
    control_in: ControlEvaluationCreate,
    db: AsyncSession = Depends(get_async_db),
    ctx: AuthContext = Depends(require_role(UserRole.INTERNAL_AUDITOR, UserRole.CONNECTOR_SERVICE)),
) -> ControlEvaluationResponse:
    record = ControlEvaluation(
        org_id=ctx.org_id,
        control_id=control_in.control_id,
        description=control_in.description,
        test_type=control_in.test_type,
        status=control_in.status,
        evidence_vault_id=control_in.evidence_vault_id,
        metrics=control_in.metrics,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


# ── SOD conflicts ─────────────────────────────────────────────────────────────

@router.get("/sod", response_model=List[SODConflictResponse])
async def list_sod_conflicts(
    limit: int = 50,
    db: AsyncSession = Depends(get_async_db),
) -> List[SODConflictResponse]:
    result = await db.execute(
        select(SODConflict).order_by(desc(SODConflict.detected_at)).limit(limit)
    )
    return result.scalars().all()


@router.post("/sod", response_model=SODConflictResponse, status_code=201)
async def report_sod_conflict(
    sod_in: SODConflictCreate,
    db: AsyncSession = Depends(get_async_db),
    ctx: AuthContext = Depends(require_role(UserRole.INTERNAL_AUDITOR, UserRole.CONNECTOR_SERVICE)),
) -> SODConflictResponse:
    record = SODConflict(
        org_id=ctx.org_id,
        user_id=sod_in.user_id,
        role_a=sod_in.role_a,
        role_b=sod_in.role_b,
        conflict_type=sod_in.conflict_type,
        risk_level=sod_in.risk_level,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


# ── Audit exceptions ──────────────────────────────────────────────────────────

@router.get("/exceptions", response_model=List[AuditExceptionResponse])
async def list_exceptions(
    limit: int = 50,
    db: AsyncSession = Depends(get_async_db),
) -> List[AuditExceptionResponse]:
    result = await db.execute(
        select(AuditException).order_by(desc(AuditException.created_at)).limit(limit)
    )
    return result.scalars().all()


@router.post("/exceptions", response_model=AuditExceptionResponse, status_code=201)
async def create_exception(
    exc_in: AuditExceptionCreate,
    db: AsyncSession = Depends(get_async_db),
    ctx: AuthContext = Depends(require_role(UserRole.INTERNAL_AUDITOR, UserRole.CONNECTOR_SERVICE)),
) -> AuditExceptionResponse:
    record = AuditException(
        org_id=ctx.org_id,
        control_test_id=exc_in.control_test_id,
        description=exc_in.description,
        owner_id=exc_in.owner_id,
        state="open",
        comments=[],
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


@router.patch(
    "/exceptions/{exception_id}/transition",
    response_model=AuditExceptionResponse,
    summary="Advance exception through its lifecycle",
)
async def transition_exception(
    exception_id: _uuid.UUID,
    body: ExceptionTransition,
    db: AsyncSession = Depends(get_async_db),
    ctx: AuthContext = Depends(require_role(UserRole.INTERNAL_AUDITOR)),
) -> AuditExceptionResponse:
    """
    Advance an audit exception to the next state in its lifecycle.

    Valid transitions::

        open → acknowledged | accepted_risk
        acknowledged → remediation_in_progress | accepted_risk
        remediation_in_progress → remediated
        remediated → closed
        accepted_risk → closed
        closed → (no further transitions)
    """
    result = await db.execute(
        select(AuditException).filter(AuditException.id == exception_id)
    )
    record = result.scalars().first()
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exception {exception_id} not found.",
        )

    current_state = _to_canonical_state(record.state or "open")
    requested_state = _to_canonical_state(body.new_state)

    allowed = _VALID_TRANSITIONS.get(current_state, [])
    if requested_state not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Cannot transition from '{current_state}' to '{requested_state}'. "
                f"Allowed next states: {allowed}"
            ),
        )

    now = datetime.now(timezone.utc)
    # Append audit trail entry to the comments log
    audit_entry: Dict[str, Any] = {
        "from_state": current_state,
        "to_state": requested_state,
        "transitioned_by": ctx.username,
        "transitioned_at": now.isoformat(),
        "comment": body.comment,
    }
    comments = list(record.comments or [])
    comments.append(audit_entry)
    record.comments = comments
    record.state = _to_storage_state(requested_state)

    db.add(
        WorkflowLog(
            org_id=ctx.org_id,
            user=ctx.username,
            action="workflow_approval",
            workflow_name="exception_lifecycle",
            resource=str(exception_id),
            stage_from=current_state,
            stage_to=requested_state,
            approval_required=True,
            approved=True,
            metadata_json={"comment": body.comment},
        )
    )

    if requested_state in ("closed",):
        record.resolved_at = now

    await db.commit()
    await db.refresh(record)
    # Respond with canonical state vocabulary expected by API clients/UAT.
    record.state = _to_canonical_state(record.state)
    return record

