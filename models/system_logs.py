"""
models/system_logs.py
Enterprise-grade request and workflow logging models.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID

from db.base import Base


class SystemLog(Base):
    """Immutable-style system log for API-level activity tracking."""

    __tablename__ = "system_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(String(50), nullable=False, index=True, default="default-org")
    user = Column(String(100), nullable=True, index=True)
    role = Column(String(80), nullable=True, index=True)
    action = Column(String(80), nullable=False, index=True)
    resource = Column(String(255), nullable=False, index=True)
    method = Column(String(10), nullable=False)
    status_code = Column(Integer, nullable=False)
    ip_address = Column(String(64), nullable=True)
    session_id = Column(String(128), nullable=True)
    user_agent = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    immutable = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )


class WorkflowLog(Base):
    """Workflow approval and process transition log entries."""

    __tablename__ = "workflow_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(String(50), nullable=False, index=True, default="default-org")
    user = Column(String(100), nullable=True, index=True)
    action = Column(String(80), nullable=False, index=True)
    workflow_name = Column(String(120), nullable=False, index=True)
    resource = Column(String(255), nullable=True)
    stage_from = Column(String(80), nullable=True)
    stage_to = Column(String(80), nullable=True)
    approval_required = Column(Boolean, nullable=False, default=False)
    approved = Column(Boolean, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
