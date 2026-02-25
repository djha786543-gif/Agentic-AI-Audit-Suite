from sqlalchemy import Column, Integer, String, DateTime, JSON
from datetime import datetime
from db.base_class import Base

class AuditEntry(Base):
    __tablename__ = "audit_vault"
    id = Column(Integer, primary_key=True, index=True)
    source_system = Column(String)
    event_type = Column(String)
    log_data = Column(String)
    metadata_json = Column(JSON)
    hash_sequence = Column(String, unique=True)
    status = Column(String, default="vaulted")
    timestamp = Column(DateTime, default=datetime.utcnow)

# Keep aliases for compatibility
EvidenceVault = AuditEntry

class ExtractionRun(Base):
    __tablename__ = "extraction_runs"
    id = Column(Integer, primary_key=True, index=True)
    status = Column(String)
    started_at = Column(DateTime, default=datetime.utcnow)
