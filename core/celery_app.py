"""
core/celery_app.py
──────────────────
Celery application factory.

WAS: empty file — worker/tasks.py imported celery_app from here and
     immediately failed with ImportError because nothing was defined.

NOW: Full Celery app with:
  - Redis broker + result backend (from settings)
  - JSON serialization only (no pickle — security requirement)
  - task_acks_late=True so a crashed worker doesn't lose a task
  - worker_prefetch_multiplier=1 for fair, one-at-a-time processing
  - Explicit task routing (extraction queue vs evaluation queue)

Start the worker from the project root:
    celery -A core.celery_app.celery_app worker --loglevel=info -Q extraction,evaluation
Start the Beat scheduler (for periodic tasks):
    celery -A core.celery_app.celery_app beat --loglevel=info
"""

from celery import Celery
from celery.signals import task_failure, task_success
import logging

from core.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "acap",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "worker.tasks",          # existing tasks module
        "worker.integrity",      # integrity verifier (Phase 3 — safe to include now)
    ],
)

celery_app.conf.update(
    # ── Serialization ─────────────────────────────────────────
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,

    # ── Reliability ───────────────────────────────────────────
    task_acks_late=True,               # ack only after task completes (not on receive)
    worker_prefetch_multiplier=1,      # one task at a time — fair processing
    task_reject_on_worker_lost=True,   # requeue if worker dies mid-task

    # ── Retry defaults ────────────────────────────────────────
    task_max_retries=3,
    task_default_retry_delay=30,       # seconds between retries

    # ── Task routing ──────────────────────────────────────────
    task_routes={
        "worker.tasks.execute_control_test":        {"queue": "extraction"},
        "worker.tasks.run_watcher_cycle":           {"queue": "extraction"},
        "worker.integrity.verify_recent_records":   {"queue": "evaluation"},
    },

    # ── Beat schedule (periodic tasks) ────────────────────────
    beat_schedule={
        "integrity-check-every-hour": {
            "task": "worker.integrity.verify_recent_records",
            "schedule": 3600.0,          # every 60 minutes
            "kwargs": {"hours_lookback": 2},
        },
    },
)


# ── Observability hooks ────────────────────────────────────────────────────

@task_failure.connect
def on_task_failure(task_id, exception, traceback, sender, **kwargs):
    logger.error(
        "celery.task_failed  task_id=%s  task=%s  error=%s",
        task_id, sender.name if sender else "unknown", str(exception),
    )


@task_success.connect
def on_task_success(sender, result, **kwargs):
    logger.info("celery.task_succeeded  task=%s", sender.name if sender else "unknown")
