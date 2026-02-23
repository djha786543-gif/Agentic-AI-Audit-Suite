"""schemas/evidence.py — Pydantic schemas matching AuditEntry model"""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Dict, Any
from datetime import datetime
import uuid


class EvidenceCreate(BaseModel):
    source_system: str
    event_type: Optional[str] = "audit_event"
    log_data: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="metadata_json")
    model_config = ConfigDict(populate_by_name=True)


class EvidenceResponse(BaseModel):
    id: uuid.UUID
    org_id: str
    source_system: str
    event_type: Optional[str] = None
    hash_sequence: Optional[str] = None
    content_hash: Optional[str] = None
    hash_verified: bool = True
    status: Optional[str] = None
    ai_confidence_score: Optional[int] = None
    recorded_at: Optional[datetime] = None
    timestamp: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class VaultSummary(BaseModel):
    total_records: int
    verified_records: int
    tampered_records: int
    low_confidence_records: int
    latest_source_system: Optional[str] = None
    latest_recorded_at: Optional[datetime] = None
