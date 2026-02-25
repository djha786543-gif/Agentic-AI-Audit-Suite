"""
worker/tasks.py
────────────────
Celery tasks for evidence extraction and control testing.

CHANGES FROM ORIGINAL:
  - celery_app import now works (core/celery_app.py is no longer empty)
  - execute_control_test() now calls vault.writer.write_evidence() which:
      (a) writes ExtractionRun ledger entry first
      (b) computes SHA-256 hash (same logic as before, now wired properly)
      (c) stores hash in content_hash column
  - run_watcher_cycle() is a Celery-native version of watcher_agent.py
    (the original watcher_agent.py is preserved for direct use too)

Both tasks use the same vault write path as the API — no separate code paths.
"""

import logging
import json
from datetime import datetime, timezone
from typing import Any

from core.celery_app import celery_app
from db.session import SessionLocal
from vault.writer import write_evidence

logger = logging.getLogger(__name__)


@celery_app.task(
    name="worker.tasks.execute_control_test",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def execute_control_test(self, control_id: str, system_path: str, mock_data: dict = None):
    """
    Execute a control test and store the result in the vault.

    The original task is preserved and upgraded:
      - Same mock_data pattern you wrote
      - Now uses vault.writer.write_evidence() for the actual DB write
        so the chain-of-custody ledger is written and the hash is computed

    Args:
        control_id:  e.g. "ACAP-WS-001"
        system_path: e.g. "Windows-Security-Logs"
        mock_data:   optional override payload (for testing)
    """
    db = SessionLocal()
    try:
        # Use provided data or the original mock from your tasks.py
        payload: dict[str, Any] = mock_data or {
            "user": "admin",
            "access_level": "root",
            "mfa_enabled": True,
            "test_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        run, record = write_evidence(
            db,
            control_id=control_id,
            source_system=system_path,
            ai_confidence_score=85,   # placeholder — Phase 4 adds real scoring
            raw_payload=payload,
            performed_by_agent_id="AGENT_ALPHA_01",
            connector_id="celery-worker",
            triggered_by="scheduler",
        )

        result = {
            "status": "success",
            "record_id": str(record.id),
            "content_hash": record.content_hash,
            "extraction_run_id": str(run.id),
        }
        logger.info("task.execute_control_test.done  %s", json.dumps(result))
        return result

    except Exception as exc:
        logger.error("task.execute_control_test.error  %s", str(exc))
        raise self.retry(exc=exc)
    finally:
        db.close()


@celery_app.task(
    name="worker.tasks.run_watcher_cycle",
    bind=True,
    max_retries=2,
)
def run_watcher_cycle(self, control_id: str = None, source_system: str = None, ai_confidence_score: int = None):
    """
    Celery-native version of watcher_agent.py.

    The watcher_agent.py script POSTs over HTTP — this task writes
    directly to the DB via vault.writer, which is more reliable for
    scheduled/internal runs (no HTTP round-trip, no port dependency).

    Called by: Celery Beat schedule  OR  direct .delay() call
    """
    import random

    db = SessionLocal()
    try:
        ctrl = control_id or f"ACAP-{random.randint(100, 999)}"
        src  = source_system or "FileSystem-Watcher"
        conf = ai_confidence_score if ai_confidence_score is not None else random.randint(60, 100)

        payload = {
            "watcher_cycle": True,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "simulated": True,
        }

        run, record = write_evidence(
            db,
            control_id=ctrl,
            source_system=src,
            ai_confidence_score=conf,
            raw_payload=payload,
            performed_by_agent_id="WATCHER-CELERY",
            connector_id="watcher-celery",
            triggered_by="scheduler",
        )

        return {
            "status": "success",
            "control_id": ctrl,
            "content_hash": record.content_hash,
        }

    except Exception as exc:
        logger.error("task.run_watcher_cycle.error  %s", str(exc))
        raise self.retry(exc=exc)
    finally:
        db.close()
