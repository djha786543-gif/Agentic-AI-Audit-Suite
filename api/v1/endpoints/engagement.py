from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from db.async_session import get_async_db
from typing import List
from schemas.engagement import EngagementCreate, EngagementResponse
from models.engagement import Engagement
from auth import Permission, require_permission

router = APIRouter(
    dependencies=[Depends(require_permission(Permission.MANAGE_ENGAGEMENTS))]
)

@router.post("/", response_model=EngagementResponse, status_code=status.HTTP_201_CREATED)
async def create_engagement(
    engagement: EngagementCreate,
    db: AsyncSession = Depends(get_async_db)
):
    new_eng = Engagement(
        audit_name=engagement.audit_name,
        entity=engagement.entity,
        period_start=engagement.period_start,
        period_end=engagement.period_end,
        status=engagement.status,
        materiality_threshold=engagement.materiality_threshold
    )
    db.add(new_eng)
    await db.commit()
    await db.refresh(new_eng)
    return new_eng

@router.get("/", response_model=List[EngagementResponse])
async def list_engagements(
    db: AsyncSession = Depends(get_async_db)
):
    from sqlalchemy.future import select
    result = await db.execute(select(Engagement))
    return result.scalars().all()
