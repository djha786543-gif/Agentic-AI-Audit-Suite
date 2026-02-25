"""
models/evaluation.py
Phase 4 — Parameterized ITGC Test Engine and SOD Matrix.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, JSON, Integer, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from db.base import Base


class ControlEvaluation(Base):
    __tablename__ = "control_evaluations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(String(50), nullable=False, index=True)
    control_id = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    test_type = Column(String(50), nullable=False)  # e.g., 'Terminated User Access', 'Open Port'
    status = Column(String(20), nullable=False, default="passed") # passed, failed, exception
    evidence_vault_id = Column(UUID(as_uuid=True), ForeignKey("audit_vault.id", ondelete="SET NULL"), nullable=True)
    metrics = Column(JSON, nullable=True)
    evaluated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class SODConflict(Base):
    __tablename__ = "sod_conflicts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(String(50), nullable=False, index=True)
    user_id = Column(String(100), nullable=False)
    role_a = Column(String(100), nullable=False)
    role_b = Column(String(100), nullable=False)
    conflict_type = Column(String(100), nullable=False) # e.g. 'Developer & Admin'
    risk_level = Column(String(20), default="High")
    detected_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    resolved = Column(Boolean, default=False)
