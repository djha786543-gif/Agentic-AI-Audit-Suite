"""
models/governance.py
Phase 5 — Continuous Assurance & Governance Layer

Stores policies, compliance framework mappings, and the risk register.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID

from db.base import Base


class GovernancePolicy(Base):
    """High-level governance policy (e.g. Acceptable Use, Change Control)."""

    __tablename__ = "governance_policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(String(50), nullable=False, index=True)
    policy_id = Column(String(50), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    owner = Column(String(100), nullable=True)
    effective_date = Column(DateTime(timezone=True), nullable=True)
    review_date = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(30), nullable=False, default="active")  # active | draft | retired
    version = Column(String(20), nullable=False, default="1.0")
    framework_refs = Column(JSON, nullable=True)   # e.g. ["SOX-302", "ISO-A.12.1"]
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ComplianceFramework(Base):
    """A supported compliance standard, e.g. SOX, ISO 27001, COBIT."""

    __tablename__ = "compliance_frameworks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(String(50), nullable=False, index=True)
    framework_id = Column(String(50), nullable=False, index=True)   # e.g. "SOX"
    name = Column(String(200), nullable=False)
    version = Column(String(30), nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class ComplianceMapping(Base):
    """Links a specific control evaluation to a compliance framework requirement."""

    __tablename__ = "compliance_mappings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(String(50), nullable=False, index=True)
    framework_id = Column(String(50), nullable=False, index=True)
    requirement_ref = Column(String(100), nullable=False)   # e.g. "SOX-404-ITGC-01"
    control_id = Column(String(100), nullable=False)
    mapping_status = Column(String(30), nullable=False, default="mapped")  # mapped | gap | partial
    notes = Column(Text, nullable=True)
    last_assessed = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class RiskRegisterEntry(Base):
    """Enterprise risk register — one row per identified risk."""

    __tablename__ = "risk_register"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(String(50), nullable=False, index=True)
    risk_id = Column(String(50), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=True)   # cyber | financial | operational | compliance
    inherent_likelihood = Column(Integer, nullable=False, default=3)   # 1-5
    inherent_impact = Column(Integer, nullable=False, default=3)       # 1-5
    residual_likelihood = Column(Integer, nullable=True)
    residual_impact = Column(Integer, nullable=True)
    risk_score = Column(Float, nullable=True)          # likelihood × impact
    risk_rating = Column(String(20), nullable=True)    # LOW | MEDIUM | HIGH | CRITICAL
    owner = Column(String(100), nullable=True)
    treatment = Column(String(30), nullable=True)      # accept | mitigate | transfer | avoid
    status = Column(String(30), nullable=False, default="open")  # open | mitigated | closed
    related_controls = Column(JSON, nullable=True)     # list of control_id strings
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
