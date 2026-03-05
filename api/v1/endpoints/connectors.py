"""
api/v1/endpoints/connectors.py
───────────────────────────────
Connector management endpoints.

GET  /connectors/health
    Returns a status summary for all registered connectors.

GET  /connectors/{connector_id}/health
    Returns detailed health for a single connector.

POST /connectors/{connector_id}/fetch
    Triggers an on-demand data fetch from a connector (INTERNAL_AUDITOR only).
    Returns a summary of records pulled.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status

from auth.context import AuthContext
from auth.rbac import UserRole, require_role
from connectors import CONNECTOR_REGISTRY

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health", summary="Health of all registered connectors")
async def all_connectors_health(
    _: AuthContext = Depends(require_role(UserRole.INTERNAL_AUDITOR, UserRole.EXTERNAL_AUDITOR)),
) -> Dict[str, Any]:
    """
    Check health for every connector in the registry.

    Returns an aggregate status (``healthy`` only if all connectors are healthy)
    and per-connector details.
    """
    results: List[Dict[str, Any]] = []
    all_healthy = True

    for connector_id, connector in CONNECTOR_REGISTRY.items():
        try:
            health = await connector.health_check()
        except Exception as exc:  # noqa: BLE001
            health = {
                "connector_id": connector_id,
                "status": "unreachable",
                "message": str(exc),
            }

        results.append(health)
        if health.get("status") != "healthy":
            all_healthy = False

    return {
        "overall_status": "healthy" if all_healthy else "degraded",
        "connector_count": len(CONNECTOR_REGISTRY),
        "connectors": results,
    }


@router.get("/{connector_id}/health", summary="Health of a single connector")
async def single_connector_health(
    connector_id: str,
    _: AuthContext = Depends(require_role(UserRole.INTERNAL_AUDITOR, UserRole.EXTERNAL_AUDITOR)),
) -> Dict[str, Any]:
    """
    Check health for the specified connector.

    Raises 404 if ``connector_id`` is not in the registry.
    """
    connector = CONNECTOR_REGISTRY.get(connector_id)
    if connector is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector '{connector_id}' not found. "
                   f"Available: {list(CONNECTOR_REGISTRY.keys())}",
        )
    try:
        return await connector.health_check()
    except Exception as exc:
        logger.error("connector.health_check.error connector=%s error=%s", connector_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Health check failed for connector '{connector_id}': {exc}",
        )


@router.post("/{connector_id}/fetch", summary="Trigger an on-demand data fetch")
async def trigger_fetch(
    connector_id: str,
    ctx: AuthContext = Depends(require_role(UserRole.INTERNAL_AUDITOR)),
) -> Dict[str, Any]:
    """
    Trigger an immediate data fetch from the specified connector.

    The ``org_id`` for tenant isolation is taken from the authenticated user's
    JWT context — it cannot be overridden by the caller.

    This is an ad-hoc pull — the Celery watcher handles scheduled fetches.
    Returns a summary of records retrieved (not the records themselves, to
    avoid large response payloads).
    """
    connector = CONNECTOR_REGISTRY.get(connector_id)
    if connector is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector '{connector_id}' not found.",
        )
    try:
        result = await connector.fetch(org_id=ctx.org_id)
        logger.info(
            "connector.fetch.complete connector=%s org=%s records=%d elapsed=%.3fs",
            connector_id,
            ctx.org_id,
            result.record_count,
            result.elapsed_seconds,
        )
        return {
            "connector_id": connector_id,
            "source_system": result.source_system,
            "org_id": ctx.org_id,
            "record_count": result.record_count,
            "success": result.success,
            "errors": result.errors,
            "elapsed_seconds": result.elapsed_seconds,
            "metadata": result.metadata,
        }
    except Exception as exc:
        logger.error("connector.fetch.error connector=%s error=%s", connector_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Fetch failed for connector '{connector_id}': {exc}",
        )
