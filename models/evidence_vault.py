"""
models/evidence_vault.py — fixed: correct Base, content_hash, extraction_run_id
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, JSON, Integer, Boolean, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.base import Base


class ExtractionRun(Base):
    __tablename__ = "extraction_runs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(String(50), nullable=False, index=True)
    connector_id = Column(String(100), nullable=False)
    source_system = Column(String(100), nullable=False)
    connector_version = Column(String(50), nullable=False, default="1.0.0")
    triggered_by = Column(String(100), nullable=False, default="api")
    status = Column(String(20), nullable=False, default="running")
    rows_extracted = Column(Integer, nullable=True)
    rows_accepted = Column(Integer, nullable=True)
    rows_rejected = Column(Integer, nullable=True, default=0)
    raw_payload_hash = Column(String(64), nullable=True)
    error_detail = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)
    evidence_records = relationship("AuditEntry", back_populates="extraction_run")


class AuditEntry(Base):
    __tablename__ = "audit_vault"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(String(50), nullable=False, index=True)
    extraction_run_id = Column(UUID(as_uuid=True),
                               ForeignKey("extraction_runs.id", ondelete="RESTRICT"),
                               nullable=True)
    extraction_run = relationship("ExtractionRun", back_populates="evidence_records")
    source_system = Column(String(100), nullable=False)
    event_type = Column(String(100), nullable=True)
    log_data = Column(String, nullable=True)
    metadata_json = Column(JSON, nullable=True)
    hash_sequence = Column(String(64), nullable=True)
    content_hash = Column(String(64), nullable=True, index=True)
    hash_verified = Column(Boolean, nullable=False, default=True)
    digital_signature = Column(String(255), nullable=True)
    ai_confidence_score = Column(Integer, nullable=True)
    status = Column(String(20), default="vaulted")
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    recorded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

EvidenceVault = AuditEntry
