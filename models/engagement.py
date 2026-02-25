from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Boolean, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime, timezone
from db.base import Base

class Engagement(Base):
    __tablename__ = "engagements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(String, index=True) # For RLS
    audit_name = Column(String, nullable=False)
    entity = Column(String, nullable=False)
    period_start = Column(DateTime)
    period_end = Column(DateTime)
    status = Column(String, default="planning") # planning / fieldwork / review / issued / closed
    materiality_threshold = Column(Integer)
    created_by = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class EngagementRole(Base):
    __tablename__ = "engagement_roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(String, index=True)
    engagement_id = Column(UUID(as_uuid=True), ForeignKey("engagements.id"), nullable=False)
    user_id = Column(String, nullable=False)  # Usually UUID of user, but String for simplicity
    role = Column(String, nullable=False) # preparer, reviewer, manager, partner

class ControlTest(Base):
    __tablename__ = "control_tests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(String, index=True)
    control_id = Column(String, nullable=False)
    engagement_id = Column(UUID(as_uuid=True), ForeignKey("engagements.id"), nullable=False)
    assigned_to = Column(String)
    testing_status = Column(String, default="pending") # pending, testing, review, completed

class Signoff(Base):
    __tablename__ = "signoffs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(String, index=True)
    engagement_id = Column(UUID(as_uuid=True), ForeignKey("engagements.id"), nullable=False)
    user_id = Column(String, nullable=False)
    role = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    digital_signature_hash = Column(String, nullable=False)
