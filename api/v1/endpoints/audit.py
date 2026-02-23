"""
api/v1/endpoints/audit.py
Evidence vault endpoints — wired to vault/writer for chain-of-custody + hash.
GET /vault is public (dashboard). POST /evidence requires JWT token.
"""
import hashlib
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, desc, select
from typing import List, Optional
import logging

from db.async_session import get_async_db
from models.evidence_vault import AuditEntry, ExtractionRun
from schemas.evidence import EvidenceCreate, EvidenceResponse, VaultSummary
from vault.writer import write_evidence, verify_hash
from core.security import get_current_user
from core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/evidence", response_model=EvidenceResponse, status_code=201)
async def submit_evidence(
    evidence_in: EvidenceCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: str = Depends(get_current_user),
):
    """Submit evidence — requires Bearer token. Use POST /auth/login first."""
    try:
        raw = {"source_system": evidence_in.source_system,
               "event_type": evidence_in.event_type,
               "log_data": evidence_in.log_data,
               **(evidence_in.metadata or {})}

        run, record = await write_evidence(
            db,
            control_id=f"ACAP-{evidence_in.event_type or 'EVT'}-001",
            source_system=evidence_in.source_system,
            ai_confidence_score=85,
            raw_payload=raw,
            performed_by_agent_id=current_user,
            connector_id=current_user,
            triggered_by="api",
            org_id="default-org"
        )
        return record
    except Exception as exc:
        logger.error("vault.write_failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/vault", response_model=List[EvidenceResponse])
async def get_vault(limit: int = 100, db: AsyncSession = Depends(get_async_db)):
    """List vault records — public, used by dashboard."""
    result = await db.execute(select(AuditEntry).order_by(desc(AuditEntry.recorded_at)).limit(limit))
    return result.scalars().all()


@router.get("/vault/summary", response_model=VaultSummary)
async def vault_summary(db: AsyncSession = Depends(get_async_db)):
    """Counts for the dashboard stats strip."""
    total = (await db.execute(select(func.count(AuditEntry.id)))).scalar() or 0
    verified = (await db.execute(select(func.count(AuditEntry.id)).filter(AuditEntry.hash_verified == True))).scalar() or 0
    low_conf = (await db.execute(select(func.count(AuditEntry.id)).filter(AuditEntry.ai_confidence_score < settings.CONFIDENCE_ALERT_THRESHOLD))).scalar() or 0
    
    result = await db.execute(select(AuditEntry).order_by(desc(AuditEntry.recorded_at)))
    latest = result.scalars().first()
    
    return VaultSummary(
        total_records=total,
        verified_records=verified,
        tampered_records=total - verified,
        low_confidence_records=low_conf,
        latest_source_system=latest.source_system if latest else None,
        latest_recorded_at=latest.recorded_at if latest else None,
    )


@router.get("/vault/{record_id}", response_model=EvidenceResponse)
async def get_vault_record(record_id: str, db: AsyncSession = Depends(get_async_db)):
    result = await db.execute(select(AuditEntry).filter(AuditEntry.id == record_id))
    record = result.scalars().first()
    
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
        
    if record.content_hash and not verify_hash(record):
        record.hash_verified = False
        await db.commit()
        await db.refresh(record)
    return record


@router.get("/runs")
async def list_runs(limit: int = 50, db: AsyncSession = Depends(get_async_db)):
    result = await db.execute(select(ExtractionRun).order_by(desc(ExtractionRun.started_at)).limit(limit))
    return result.scalars().all()


@router.post("/runs/heartbeat", status_code=201)
async def record_heartbeat(db: AsyncSession = Depends(get_async_db)):
    from datetime import datetime, timezone
    new_run = ExtractionRun(
        org_id="default-org",
        connector_id="watcher_agent_heartbeat",
        source_system="watcher_agent",
        status="Success",
        started_at=datetime.now(timezone.utc)
    )
    db.add(new_run)
    await db.commit()
    return {"status": "heartbeat recorded"}


@router.get("/runs/count")
async def get_runs_count(db: AsyncSession = Depends(get_async_db)):
    count = (await db.execute(select(func.count(ExtractionRun.id)))).scalar() or 0
    return {"count": count}
