from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid

class ControlEvaluationCreate(BaseModel):
    control_id: str
    description: Optional[str] = None
    test_type: str
    status: str
    evidence_vault_id: Optional[uuid.UUID] = None
    metrics: Optional[Dict[str, Any]] = None

class ControlEvaluationResponse(BaseModel):
    id: uuid.UUID
    org_id: str
    control_id: str
    description: Optional[str] = None
    test_type: str
    status: str
    evidence_vault_id: Optional[uuid.UUID] = None
    metrics: Optional[Dict[str, Any]] = None
    evaluated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class SODConflictCreate(BaseModel):
    user_id: str
    role_a: str
    role_b: str
    conflict_type: str
    risk_level: str = "High"

class SODConflictResponse(BaseModel):
    id: uuid.UUID
    org_id: str
    user_id: str
    role_a: str
    role_b: str
    conflict_type: str
    risk_level: str
    detected_at: datetime
    resolved: bool
    model_config = ConfigDict(from_attributes=True)

class AuditExceptionCreate(BaseModel):
    control_test_id: uuid.UUID
    description: str
    owner_id: str

class AuditExceptionResponse(BaseModel):
    id: uuid.UUID
    org_id: str
    control_test_id: Optional[uuid.UUID] = None
    description: str
    state: str
    owner_id: str
    comments: List[Any]
    created_at: datetime
    resolved_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)
