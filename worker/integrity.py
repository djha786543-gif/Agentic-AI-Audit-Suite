"""
worker/integrity.py
────────────────────
Celery Beat task: periodic re-verification of vault record hashes.

Runs every 60 minutes (configured in core/celery_app.py beat_schedule).

For every EvidenceVault record written in the last N hours:
  1. Re-compute SHA-256 of raw_payload
  2. Compare to stored content_hash
  3. If mismatch → set hash_verified=False and log CRITICAL

This is the tamper detection that makes the vault audit-admissible.
The dashboard reads hash_verified and fires the red pulse if any are False.
"""

import logging
from datetime import datetime, timezone, timedelta

from core.celery_app import celery_app
from db.session import SessionLocal
from models.evidence_vault import EvidenceVault
from vault.writer import verify_hash

logger = logging.getLogger(__name__)


@celery_app.task(name="worker.integrity.verify_recent_records")
def verify_recent_records(hours_lookback: int = 2) -> dict:
    """
    Re-verify all vault records written in the last `hours_lookback` hours.

    Returns a summary dict: { checked, passed, failed, already_flagged }
    """
    from sqlalchemy import text
    db = SessionLocal()
    db.execute(
        text("SELECT set_config('app.current_tenant', :tenant, true)"),
        {"tenant": "default-org"},
    )
    checked = passed = failed = already_flagged = 0

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_lookback)

        records = (
            db.query(EvidenceVault)
            .filter(EvidenceVault.recorded_at >= cutoff)
            .all()
        )

        for record in records:
            checked += 1

            if not record.hash_verified:
                already_flagged += 1
                continue   # already marked — skip re-verification

            ok = verify_hash(record)
            if ok:
                passed += 1
            else:
                failed += 1
                record.hash_verified = False
                logger.critical(
                    "integrity.tamper_detected  "
                    "record_id=%s  control_id=%s  stored_hash=%s",
                    record.id,
                    record.event_type,
                    record.content_hash,
                )

        if failed > 0:
            db.commit()

        summary = {
            "checked": checked,
            "passed": passed,
            "failed": failed,
            "already_flagged": already_flagged,
            "ran_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info("integrity.verify_complete  %s", summary)
        return summary

    except Exception as exc:
        logger.error("integrity.verify_error  %s", str(exc))
        db.rollback()
        raise
    finally:
        db.close()
