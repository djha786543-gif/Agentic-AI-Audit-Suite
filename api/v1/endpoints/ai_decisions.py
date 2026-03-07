"""api/v1/endpoints/ai_decisions.py
Explainable AI decision retrieval endpoints.
"""
from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.context import AuthContext
from auth.rbac import Permission, require_permission
from db.async_session import get_async_db
from models.ai_decision import AIDecision

router = APIRouter()


@router.get("/{decision_id}", summary="Get explainable AI decision by id")
async def get_ai_decision(
    decision_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    _: AuthContext = Depends(require_permission(Permission.VIEW_AUDIT_LOGS)),
) -> Dict[str, Any]:
    result = await db.execute(
        select(AIDecision).filter(AIDecision.id == decision_id)
    )
    record = result.scalars().first()
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AI decision {decision_id} not found",
        )

    return {
        "id": str(record.id),
        "org_id": record.org_id,
        "decision_type": record.decision_type,
        "resource": record.resource,
        "decision_summary": record.decision_summary,
        "confidence_score": record.confidence_score,
        "reasoning_trace": record.reasoning_trace,
        "data_sources": (record.source_data_reference or {}).get("data_sources", []),
        "timestamp": record.created_at.isoformat() if record.created_at else None,
        "model_version": record.model_used,
        "input_reference": (record.source_data_reference or {}).get("input_reference"),
        "reasoning_chain": (record.source_data_reference or {}).get("reasoning_chain"),
        "explanation_text": record.reasoning_trace,
        "metadata": record.source_data_reference,
    }
