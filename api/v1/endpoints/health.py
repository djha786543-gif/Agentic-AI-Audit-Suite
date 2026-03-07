"""
api/v1/endpoints/health.py
───────────────────────────
System health check endpoints.

GET /health        — basic liveness probe (load balancer / Docker healthcheck)
GET /health/ready  — readiness probe: checks DB connectivity and Redis
"""

import asyncio

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime, timezone
import logging
import redis

from db.async_session import get_async_db
from core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/health",
    summary="Liveness probe",
    description="Returns 200 if the process is running. Used by Docker HEALTHCHECK.",
    tags=["health"],
)
def liveness():
    return {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "acap-api",
    }


@router.get(
    "/health/ready",
    summary="Readiness probe",
    description="Returns 200 only when the DB is reachable. Used by docker-compose depends_on.",
    tags=["health"],
)
async def readiness(
    response: Response,
    db: AsyncSession = Depends(get_async_db),
):
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:
        logger.error("health.db_unreachable  error=%s", str(exc))
        db_status = "error"

    try:
        redis_client = redis.from_url(settings.REDIS_URL)
        await asyncio.to_thread(redis_client.ping)
        redis_status = "ok"
    except Exception as exc:
        logger.error("health.redis_unreachable error=%s", str(exc))
        redis_status = "error"

    overall = "ready" if db_status == "ok" and redis_status == "ok" else "not_ready"
    if overall != "ready":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": overall,
        "database": db_status,
        "redis": redis_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
