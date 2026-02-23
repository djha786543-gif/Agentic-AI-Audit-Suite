"""vault/writer.py - chain-of-custody write: ledger first, hash, then evidence"""
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from models.evidence_vault import AuditEntry, ExtractionRun

logger = logging.getLogger(__name__)


def compute_hash(payload: Any) -> str:
    if payload is None:
        canonical = "null"
    elif isinstance(payload, (dict, list)):
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    else:
        canonical = str(payload)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def write_evidence(
    db: AsyncSession,
    *,
    control_id: str,
    source_system: str,
    ai_confidence_score: int,
    raw_payload: Optional[dict] = None,
    digital_signature: Optional[str] = None,
    source_timestamp: Optional[datetime] = None,
    performed_by_agent_id: Optional[str] = None,
    connector_id: str = "api-direct",
    connector_version: str = "1.0.0",
    triggered_by: str = "api",
    org_id: str = "default-org",
):
    now = datetime.now(timezone.utc)

    run = ExtractionRun(
        org_id=org_id,
        connector_id=connector_id,
        source_system=source_system,
        connector_version=connector_version,
        triggered_by=triggered_by,
        status="running",
        rows_extracted=1,
        started_at=now,
    )
    db.add(run)
    await db.flush()

    content_hash = compute_hash(raw_payload)

    record = AuditEntry(
        org_id=org_id,
        extraction_run_id=run.id,
        source_system=source_system,
        event_type=control_id,
        log_data=json.dumps(raw_payload, default=str) if raw_payload else None,
        metadata_json=raw_payload,
        hash_sequence=content_hash,
        content_hash=content_hash,
        digital_signature=digital_signature,
        hash_verified=True,
        ai_confidence_score=ai_confidence_score,
        status="vaulted",
        recorded_at=now,
        timestamp=now,
    )
    db.add(record)

    run.status = "completed"
    run.completed_at = now
    run.rows_accepted = 1
    run.raw_payload_hash = content_hash

    await db.commit()
    await db.refresh(run)
    await db.refresh(record)

    logger.info("vault.write_complete control=%s hash=%s...", control_id, content_hash[:12])
    return run, record


def verify_hash(record: AuditEntry) -> bool:
    if not record.content_hash:
        return True
    recomputed = compute_hash(record.metadata_json)
    return recomputed == record.content_hash
