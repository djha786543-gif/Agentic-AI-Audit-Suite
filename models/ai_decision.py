"""
models/ai_decision.py
Structured explainability records for AI-generated decisions.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID

from db.base import Base


class AIDecision(Base):
    """Canonical explainability payload persisted for audit defensibility."""

    __tablename__ = "ai_decisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(String(50), nullable=False, index=True, default="default-org")
    decision_type = Column(String(80), nullable=False, index=True)
    resource = Column(String(255), nullable=True, index=True)
    decision_summary = Column(Text, nullable=False)
    confidence_score = Column(Float, nullable=True)
    source_data_reference = Column(JSON, nullable=True)
    reasoning_trace = Column(Text, nullable=True)
    model_used = Column(String(120), nullable=True)
    generated_by = Column(String(100), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
