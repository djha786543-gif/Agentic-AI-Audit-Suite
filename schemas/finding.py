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
    org_id: Optional[str] = None
    engagement_id: Optional[UUID] = None
    created_at: Optional[datetime] = None
    remediation_owner: Optional[str] = None
    remediation_due_date: Optional[datetime] = None
    logic_breakdown: Optional[str] = None
    reperformance_payload: Optional[dict] = None
    
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


class RemediationAssignment(BaseModel):
    remediation_owner: str
    remediation_due_date: datetime


class ReperformanceRequest(BaseModel):
    include_prompt: bool = True

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
