from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime

class EvidenceCreate(BaseModel):
    source_system: str
    event_type: str
    log_data: str
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="metadata_json")
    model_config = ConfigDict(populate_by_name=True)

class EvidenceResponse(BaseModel):
    id: int
    source_system: str
    hash_sequence: str
    status: str # Matches the model
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)
