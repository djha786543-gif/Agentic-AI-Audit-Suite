"""
models/reports.py
Phase 6 — Enterprise Reporting

Report definitions, executed report runs, and optional schedules.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID

from db.base import Base


class ReportDefinition(Base):
    """
    A reusable report template (e.g. "SOX 404 Quarterly Summary",
    "Executive Risk Dashboard", "Engagement Workpaper Package").
    """

    __tablename__ = "report_definitions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(String(50), nullable=False, index=True)
    report_type = Column(String(50), nullable=False)
    # executive_summary | compliance_status | audit_findings | sod_matrix |
    # engagement_package | risk_register | continuous_assurance
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    parameters = Column(JSON, nullable=True)     # e.g. {"period_start": "...", "period_end": "..."}
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(100), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ReportRun(Base):
    """
    An executed instance of a report definition. Stores the generated payload
    as JSON so it can be re-retrieved without re-running the query.
    """

    __tablename__ = "report_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(String(50), nullable=False, index=True)
    report_definition_id = Column(UUID(as_uuid=True), nullable=True)
    report_type = Column(String(50), nullable=False)
    name = Column(String(200), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    # pending | running | complete | failed
    parameters = Column(JSON, nullable=True)
    result_payload = Column(JSON, nullable=True)    # the generated report data
    generated_by = Column(String(100), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class ReportSchedule(Base):
    """
    Recurring schedule that triggers a report run automatically via Celery Beat.
    """

    __tablename__ = "report_schedules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(String(50), nullable=False, index=True)
    report_definition_id = Column(UUID(as_uuid=True), nullable=False)
    cron_expression = Column(String(100), nullable=False, default="0 8 * * 1")
    # Default: every Monday at 08:00
    is_active = Column(Boolean, nullable=False, default=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String(100), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
