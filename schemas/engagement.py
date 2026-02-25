from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID

# Engagement Base
class EngagementBase(BaseModel):
    audit_name: str
    entity: str
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    status: Optional[str] = "planning"
    materiality_threshold: Optional[int] = None

class EngagementCreate(EngagementBase):
    pass

class EngagementResponse(EngagementBase):
    id: UUID
    org_id: str
    created_by: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# Control Test Models
class ControlTestBase(BaseModel):
    control_id: str
    assigned_to: Optional[str] = None
    testing_status: Optional[str] = "pending"

class ControlTestCreate(ControlTestBase):
    engagement_id: UUID

class ControlTestResponse(ControlTestBase):
    id: UUID
    engagement_id: UUID
    
    class Config:
        from_attributes = True

class SignoffBase(BaseModel):
    user_id: str
    role: str
    digital_signature_hash: str

class SignoffCreate(SignoffBase):
    engagement_id: UUID

class SignoffResponse(SignoffBase):
    id: UUID
    engagement_id: UUID
    timestamp: datetime
    
    class Config:
        from_attributes = True
