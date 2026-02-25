from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID

class FindingBase(BaseModel):
    control_id: str
    severity: str
    description: str
    status: Optional[str] = "open"

class FindingCreate(FindingBase):
    engagement_id: UUID

class FindingResponse(FindingBase):
    id: UUID
    org_id: str
    engagement_id: UUID
    created_at: datetime
    
    class Config:
        from_attributes = True

class ManagementResponseBase(BaseModel):
    response_text: str
    responsible_owner: str
    target_date: Optional[datetime] = None

class ManagementResponseCreate(ManagementResponseBase):
    finding_id: UUID

class ManagementResponseResponse(ManagementResponseBase):
    id: UUID
    org_id: str
    finding_id: UUID
    submitted_on: datetime
    
    class Config:
        from_attributes = True

class RetestBase(BaseModel):
    retest_result: str
    retested_by: str

class RetestCreate(RetestBase):
    finding_id: UUID

class RetestResponse(RetestBase):
    id: UUID
    org_id: str
    finding_id: UUID
    retest_date: datetime
    
    class Config:
        from_attributes = True
