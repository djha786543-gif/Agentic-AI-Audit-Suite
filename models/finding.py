from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from db.base import Base

class Finding(Base):
    __tablename__ = "findings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(String, index=True) # for RLS
    engagement_id = Column(UUID(as_uuid=True), index=True)
    control_id = Column(String, index=True)
    severity = Column(String) # low, medium, high, critical
    description = Column(Text)
    status = Column(String, default="open") # open, management_response, remediation, retest, closed
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # New Evidence and Accuracy tracking fields
    from sqlalchemy.dialects.postgresql import JSONB
    from sqlalchemy.types import JSON
    evidence = Column(JSON, nullable=True) # Fallback JSON works in sqlite/pg
    auditor_verdict = Column(String, nullable=True) # "confirmed" | "false_positive" | "needs_review"
    verdict_by = Column(String, nullable=True)
    verdict_timestamp = Column(DateTime, nullable=True)
    verdict_notes = Column(Text, nullable=True)
    remediation_owner = Column(String, nullable=True)
    remediation_due_date = Column(DateTime, nullable=True)
    logic_breakdown = Column(Text, nullable=True)
    reperformance_payload = Column(JSON, nullable=True)

class ManagementResponse(Base):
    __tablename__ = "management_responses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(String, index=True)
    finding_id = Column(UUID(as_uuid=True), ForeignKey("findings.id"), nullable=False)
    response_text = Column(Text)
    responsible_owner = Column(String)
    target_date = Column(DateTime)
    submitted_on = Column(DateTime, default=datetime.utcnow)

class Retest(Base):
    __tablename__ = "retests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(String, index=True)
    finding_id = Column(UUID(as_uuid=True), ForeignKey("findings.id"), nullable=False)
    retest_date = Column(DateTime, default=datetime.utcnow)
    retest_result = Column(String) # pass, fail
    retested_by = Column(String) # which agent or user
