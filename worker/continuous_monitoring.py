"""
worker/continuous_monitoring.py
Phase 5 — Continuous Assurance & Governance Layer

Celery task that runs on a configurable schedule (default: every 30 minutes).
It evaluates all active AlertRules against current DB state and raises
ComplianceAlerts whenever a threshold is breached.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from core.celery_app import celery_app
from db.async_session import AsyncSessionLocal

logger = logging.getLogger(__name__)


# ── Metric collectors ──────────────────────────────────────────────────────────

async def _collect_metric(db, metric: str) -> int:
    """Return the current integer value for *metric* name."""
    from sqlalchemy import select, func
    from models.evaluation import ControlEvaluation, SODConflict
    from models.exceptions import AuditException
    from models.finding import Finding
    from models.alerts import ComplianceAlert

    if metric == "failed_controls_count":
        result = await db.execute(
            select(func.count()).select_from(ControlEvaluation).filter(
                ControlEvaluation.status == "failed"
            )
        )
        return result.scalar() or 0

    if metric == "open_exceptions_count":
        result = await db.execute(
            select(func.count()).select_from(AuditException).filter(
                AuditException.state != "closed"
            )
        )
        return result.scalar() or 0

    if metric == "critical_findings_count":
        result = await db.execute(
            select(func.count()).select_from(Finding).filter(
                Finding.severity == "critical"
            )
        )
        return result.scalar() or 0

    if metric == "sod_conflicts_count":
        result = await db.execute(
            select(func.count()).select_from(SODConflict).filter(
                SODConflict.resolved.is_(False)
            )
        )
        return result.scalar() or 0

    if metric == "open_alerts_count":
        result = await db.execute(
            select(func.count()).select_from(ComplianceAlert).filter(
                ComplianceAlert.status == "open"
            )
        )
        return result.scalar() or 0

    logger.warning("continuous_monitoring: unknown metric '%s'", metric)
    return 0


def _evaluate_operator(value: int, operator: str, threshold: int) -> bool:
    ops = {
        "gte": value >= threshold,
        "gt":  value >  threshold,
        "lte": value <= threshold,
        "lt":  value <  threshold,
        "eq":  value == threshold,
    }
    return ops.get(operator, False)


# ── Main async logic ───────────────────────────────────────────────────────────

async def _run_monitoring_sweep() -> dict[str, Any]:
    from sqlalchemy import select, text
    from models.alerts import AlertRule, ComplianceAlert

    alerts_raised = 0
    alerts_checked = 0

    async with AsyncSessionLocal() as db:
        await db.execute(
            text("SET LOCAL app.current_tenant = :tenant"),
            {"tenant": "default-org"},
        )

        # Fetch all active rules
        rules_result = await db.execute(
            select(AlertRule).filter(AlertRule.is_active.is_(True))
        )
        rules = rules_result.scalars().all()

        for rule in rules:
            alerts_checked += 1
            value = await _collect_metric(db, rule.metric)
            if _evaluate_operator(value, rule.operator, rule.threshold):
                # Check if a duplicate open alert already exists for this rule
                dup_result = await db.execute(
                    select(ComplianceAlert).filter(
                        ComplianceAlert.alert_rule_id == rule.id,
                        ComplianceAlert.status == "open",
                    )
                )
                if dup_result.scalars().first() is not None:
                    logger.debug(
                        "monitoring: rule '%s' triggered but open alert already exists — skipping",
                        rule.rule_id,
                    )
                    continue

                alert = ComplianceAlert(
                    org_id=rule.org_id,
                    alert_rule_id=rule.id,
                    title=f"[Auto] {rule.name}",
                    description=(
                        f"Rule '{rule.rule_id}' triggered: "
                        f"metric '{rule.metric}' = {value} "
                        f"(threshold {rule.operator} {rule.threshold})"
                    ),
                    severity=rule.severity,
                    metric_value=value,
                    status="open",
                )
                db.add(alert)
                alerts_raised += 1
                logger.warning(
                    "monitoring: alert raised — rule=%s metric=%s value=%d",
                    rule.rule_id, rule.metric, value,
                )

        await db.commit()

    return {
        "rules_checked": alerts_checked,
        "alerts_raised": alerts_raised,
        "swept_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Celery task ────────────────────────────────────────────────────────────────

@celery_app.task(
    name="worker.continuous_monitoring.run_monitoring_sweep",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def run_monitoring_sweep(self):
    """
    Evaluate all active AlertRules and raise ComplianceAlerts on threshold breach.
    Scheduled every 30 minutes by Celery Beat.
    """
    try:
        result = asyncio.run(_run_monitoring_sweep())
        logger.info(
            "continuous_monitoring.sweep.done  rules_checked=%d  alerts_raised=%d",
            result["rules_checked"],
            result["alerts_raised"],
        )
        return result
    except Exception as exc:
        logger.error("continuous_monitoring.sweep.error  %s", str(exc))
        raise self.retry(exc=exc)
