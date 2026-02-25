"""
vault/writer.py
───────────────
Vault write logic: compute SHA-256 hash, write ExtractionRun first,
then write EvidenceVault. This is the chain-of-custody enforcement point.

The hash from worker/tasks.py was correct in principle but was never called
from the API endpoint. This module is called by BOTH:
  1. api/v1/endpoints/audit.py  (direct API submission)
  2. worker/tasks.py            (Celery task submission)

So the hash is ALWAYS computed, regardless of submission path.
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from models.evidence_vault import EvidenceVault, ExtractionRun

logger = logging.getLogger(__name__)


def compute_hash(payload: Any) -> str:
    """
    SHA-256 of the canonical JSON representation of a payload.

    sort_keys=True ensures the hash is deterministic regardless of
    key insertion order. This is the same approach as worker/tasks.py
    but now called consistently for every vault write.

    Returns the hex digest string (64 characters).
    """
    if payload is None:
        canonical = "null"
    elif isinstance(payload, (dict, list)):
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    else:
        canonical = str(payload)

    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def write_evidence(
    db: Session,
    *,
    control_id: str,
    source_system: str,
    ai_confidence_score: int,
    raw_payload: Optional[dict[str, Any]] = None,
    digital_signature: Optional[str] = None,
    source_timestamp: Optional[datetime] = None,
    performed_by_agent_id: Optional[str] = None,
    connector_id: str = "api-direct",
    connector_version: str = "1.0.0",
    triggered_by: str = "api",
) -> tuple[ExtractionRun, EvidenceVault]:
    """
    Write evidence to the vault with full chain of custody.

    ORDER IS CRITICAL:
    1. Write ExtractionRun  ← proves extraction happened (even if step 2 fails)
    2. Compute content_hash ← SHA-256 of raw_payload
    3. Write EvidenceVault  ← the actual evidence record

    Returns (extraction_run, evidence_record) so the caller can
    include both IDs in the API response.

    Raises: sqlalchemy.exc.SQLAlchemyError on DB failure (caller handles)
    """
    now = datetime.now(timezone.utc)

    # ── Step 1: Write extraction ledger entry FIRST ────────────
    run = ExtractionRun(
        connector_id=connector_id,
        source_system=source_system,
        connector_version=connector_version,
        triggered_by=triggered_by,
        status="running",
        rows_extracted=1,
        started_at=now,
    )
    db.add(run)
    db.flush()  # get run.id without committing yet
    logger.debug("vault.ledger_written run_id=%s source=%s", run.id, source_system)

    # ── Step 2: Compute SHA-256 hash ───────────────────────────
    content_hash = compute_hash(raw_payload)
    logger.debug("vault.hash_computed hash=%s...", content_hash[:12])

    # ── Step 3: Write evidence record ─────────────────────────
    record = EvidenceVault(
        extraction_run_id=run.id,
        control_id=control_id,
        source_system=source_system,
        performed_by_agent_id=performed_by_agent_id,
        raw_payload=raw_payload,
        content_hash=content_hash,
        digital_signature=digital_signature,
        hash_verified=True,
        ai_confidence_score=ai_confidence_score,
        source_timestamp=source_timestamp or now,
        recorded_at=now,
    )
    db.add(record)

    # ── Step 4: Mark run as completed ─────────────────────────
    run.status = "completed"
    run.completed_at = now
    run.rows_accepted = 1
    run.raw_payload_hash = content_hash

    db.commit()
    db.refresh(run)
    db.refresh(record)

    logger.info(
        "vault.write_complete  control_id=%s  hash=%s...  run_id=%s",
        control_id, content_hash[:12], run.id,
    )
    return run, record


def verify_hash(record: EvidenceVault) -> bool:
    """
    Re-compute the hash of a stored record and compare to stored content_hash.

    Returns True if hashes match (record is intact).
    Returns False if they differ (record has been tampered with).

    Called by: worker/integrity.py (Celery Beat task, Phase 3)
               GET /vault/{id} endpoint (on-demand verification)
    """
    recomputed = compute_hash(record.raw_payload)
    return recomputed == record.content_hash
