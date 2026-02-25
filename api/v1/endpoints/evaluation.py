from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List

from db.async_session import get_async_db
from models.evaluation import ControlEvaluation, SODConflict
from models.exceptions import AuditException
from schemas.evaluation import (
    ControlEvaluationCreate, ControlEvaluationResponse,
    SODConflictCreate, SODConflictResponse,
    AuditExceptionCreate, AuditExceptionResponse
)

router = APIRouter()

@router.get("/controls", response_model=List[ControlEvaluationResponse])
async def list_controls(limit: int = 50, db: AsyncSession = Depends(get_async_db)):
    result = await db.execute(select(ControlEvaluation).order_by(desc(ControlEvaluation.evaluated_at)).limit(limit))
    return result.scalars().all()

@router.post("/controls", response_model=ControlEvaluationResponse, status_code=201)
async def create_control_evaluation(control_in: ControlEvaluationCreate, db: AsyncSession = Depends(get_async_db)):
    record = ControlEvaluation(
        org_id="default-org",
        control_id=control_in.control_id,
        description=control_in.description,
        test_type=control_in.test_type,
        status=control_in.status,
        evidence_vault_id=control_in.evidence_vault_id,
        metrics=control_in.metrics
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


@router.get("/sod", response_model=List[SODConflictResponse])
async def list_sod_conflicts(limit: int = 50, db: AsyncSession = Depends(get_async_db)):
    result = await db.execute(select(SODConflict).order_by(desc(SODConflict.detected_at)).limit(limit))
    return result.scalars().all()

@router.post("/sod", response_model=SODConflictResponse, status_code=201)
async def report_sod_conflict(sod_in: SODConflictCreate, db: AsyncSession = Depends(get_async_db)):
    record = SODConflict(
        org_id="default-org",
        user_id=sod_in.user_id,
        role_a=sod_in.role_a,
        role_b=sod_in.role_b,
        conflict_type=sod_in.conflict_type,
        risk_level=sod_in.risk_level
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


@router.get("/exceptions", response_model=List[AuditExceptionResponse])
async def list_exceptions(limit: int = 50, db: AsyncSession = Depends(get_async_db)):
    result = await db.execute(select(AuditException).order_by(desc(AuditException.created_at)).limit(limit))
    return result.scalars().all()

@router.post("/exceptions", response_model=AuditExceptionResponse, status_code=201)
async def create_exception(exc_in: AuditExceptionCreate, db: AsyncSession = Depends(get_async_db)):
    record = AuditException(
        org_id="default-org",
        control_test_id=exc_in.control_test_id,
        description=exc_in.description,
        owner_id=exc_in.owner_id
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record
