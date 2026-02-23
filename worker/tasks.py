"""
worker/tasks.py
Celery tasks for evidence extraction and control testing.
"""

import logging
import json
import asyncio
from datetime import datetime, timezone
from typing import Any

from core.celery_app import celery_app
from db.async_session import AsyncSessionLocal
from vault.writer import write_evidence

logger = logging.getLogger(__name__)


@celery_app.task(
    name="worker.tasks.execute_control_test",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def execute_control_test(self, control_id: str, system_path: str, mock_data: dict = None):
    async def _do_work():
        from sqlalchemy import text
        async with AsyncSessionLocal() as db:
            await db.execute(text("SET LOCAL app.current_tenant = 'default-org'"))
            payload: dict[str, Any] = mock_data or {
                "user": "admin",
                "access_level": "root",
                "mfa_enabled": True,
                "test_timestamp": datetime.now(timezone.utc).isoformat(),
            }

            run, record = await write_evidence(
                db,
                control_id=control_id,
                source_system=system_path,
                ai_confidence_score=85,
                raw_payload=payload,
                performed_by_agent_id="AGENT_ALPHA_01",
                connector_id="celery-worker",
                triggered_by="scheduler",
                org_id="default-org"
            )

            return {
                "status": "success",
                "record_id": str(record.id),
                "content_hash": record.content_hash,
                "extraction_run_id": str(run.id),
            }

    try:
        result = asyncio.run(_do_work())
        logger.info("task.execute_control_test.done  %s", json.dumps(result))
        return result
    except Exception as exc:
        logger.error("task.execute_control_test.error  %s", str(exc))
        raise self.retry(exc=exc)


@celery_app.task(
    name="worker.tasks.run_watcher_cycle",
    bind=True,
    max_retries=2,
)
def run_watcher_cycle(self, control_id: str = None, source_system: str = None, ai_confidence_score: int = None):
    async def _do_async_work():
        from sqlalchemy import text
        import random
        async with AsyncSessionLocal() as db:
            await db.execute(text("SET LOCAL app.current_tenant = 'default-org'"))
            ctrl = control_id or f"ACAP-{random.randint(100, 999)}"
            src  = source_system or "FileSystem-Watcher"
            conf = ai_confidence_score if ai_confidence_score is not None else random.randint(60, 100)

            payload = {
                "watcher_cycle": True,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "simulated": True,
            }

            run, record = await write_evidence(
                db,
                control_id=ctrl,
                source_system=src,
                ai_confidence_score=conf,
                raw_payload=payload,
                performed_by_agent_id="WATCHER-CELERY",
                connector_id="watcher-celery",
                triggered_by="scheduler",
                org_id="default-org"
            )

            return {
                "status": "success",
                "control_id": ctrl,
                "content_hash": record.content_hash,
            }

    try:
        return asyncio.run(_do_async_work())
    except Exception as exc:
        logger.error("task.run_watcher_cycle.error  %s", str(exc))
        raise self.retry(exc=exc)
