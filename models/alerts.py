"""
models/alerts.py
Phase 5 — Continuous Assurance & Governance Layer

Alert rules (threshold-based) and raised compliance alerts.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID

from db.base import Base


class AlertRule(Base):
    """
    Configurable threshold rule that the continuous-monitoring Celery task
    evaluates on each sweep.
    """

    __tablename__ = "alert_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(String(50), nullable=False, index=True)
    rule_id = Column(String(50), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    # What to measure: "failed_controls_count" | "open_exceptions_count" |
    #                  "critical_findings_count" | "sod_conflicts_count"
    metric = Column(String(100), nullable=False)
    operator = Column(String(10), nullable=False, default="gte")   # gte | gt | lte | lt | eq
    threshold = Column(Integer, nullable=False, default=1)
    severity = Column(String(20), nullable=False, default="HIGH")  # LOW | MEDIUM | HIGH | CRITICAL
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class ComplianceAlert(Base):
    """
    An alert raised by the continuous-monitoring task or manually by an auditor.
    """

    __tablename__ = "compliance_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(String(50), nullable=False, index=True)
    alert_rule_id = Column(UUID(as_uuid=True), nullable=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String(20), nullable=False, default="HIGH")
    # open | acknowledged | resolved
    status = Column(String(30), nullable=False, default="open")
    metric_value = Column(Integer, nullable=True)      # observed value that triggered the rule
    affected_controls = Column(JSON, nullable=True)    # list of control_id strings
    acknowledged_by = Column(String(100), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(String(100), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
