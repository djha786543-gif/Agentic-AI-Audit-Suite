from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from db.base import Base

class EvidenceArtifact(Base):
    __tablename__ = "evidence_artifacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(String, index=True) # for RLS
    engagement_id = Column(UUID(as_uuid=True), index=True) # Can refer to engagement, nullable early on
    artifact_type = Column(String, nullable=False) # e.g., finding, dataset, log, workpaper
    file_path = Column(String, nullable=False) # Maps to Immutable Storage like S3 WORM / Azure Blob
    sha256_hash = Column(String, nullable=False)
    created_timestamp = Column(DateTime, default=datetime.utcnow)
    created_by_agent = Column(String, nullable=False)
    locked = Column(Boolean, default=True) # Immutable flag
