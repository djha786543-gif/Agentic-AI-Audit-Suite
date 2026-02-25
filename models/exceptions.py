"""
models/exceptions.py
Phase 4 — Exception workflows (acknowledge / remediate / accept)
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, JSON, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from db.base import Base


class AuditException(Base):
    __tablename__ = "audit_exceptions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(String(50), nullable=False, index=True)
    control_test_id = Column(UUID(as_uuid=True), ForeignKey("control_evaluations.id", ondelete="CASCADE"), nullable=True)
    description = Column(Text, nullable=False)
    state = Column(String(20), default="open") # open, acknowledged, remediated, accepted
    owner_id = Column(String(100), nullable=False) # e.g., 'User123' or 'AutoAgent'
    comments = Column(JSON, default=list) # Audit log of workflow steps
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime(timezone=True), nullable=True)
