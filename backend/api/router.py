"""backend/api/router.py
Enterprise API layer that preserves existing endpoint compatibility.
"""
from __future__ import annotations

from fastapi import APIRouter

from api.v1.api_router import api_router as existing_api_router

router = APIRouter()


@router.get("/backend/health", tags=["Backend"])
async def backend_health() -> dict[str, str]:
    return {"status": "ok", "service": "acap-enterprise-backend"}


# Preserve current UI contracts by mounting existing API routes unchanged.
router.include_router(existing_api_router, prefix="/api/v1")
