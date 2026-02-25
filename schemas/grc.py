from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import date
from uuid import UUID

class GRCControlResponse(BaseModel):
    control_id: str
    description: str
    frequency: str
    owner: str

class GRCTestResult(BaseModel):
    control_id: str
    testing_date: date
    result: str # Passed, Failed
    exceptions: int
    workpaper_link: str

class GRCIssue(BaseModel):
    control_id: str
    severity: str
    description: str
    remediation_recommendation: str
