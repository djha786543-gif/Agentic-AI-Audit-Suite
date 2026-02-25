from sqlalchemy import Column, String, Integer, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
import uuid
from db.base import Base

class ControlLibrary(Base):
    __tablename__ = "control_library"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(String, index=True) # for RLS
    control_id = Column(String, unique=True, index=True)
    control_frequency = Column(String)  # daily, weekly, monthly, annual
    control_type = Column(String)       # preventive / detective
    population_source = Column(String)

class TestProcedure(Base):
    __tablename__ = "test_procedures"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(String, index=True)
    control_id = Column(String, ForeignKey("control_library.control_id"))
    procedure_description = Column(Text)
    audit_standard_reference = Column(String) # SOX 404, ISO 27001, etc.

class SamplingRule(Base):
    __tablename__ = "sampling_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(String, index=True)
    control_id = Column(String, ForeignKey("control_library.control_id"))
    sampling_type = Column(String) # full / random / risk-based
    sample_size = Column(Integer)
    rationale = Column(Text) # Explicit reasoning for why this sample counts as audit evidence
