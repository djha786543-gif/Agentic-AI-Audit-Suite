import hashlib
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.session import get_db
from models.evidence_vault import AuditEntry
from schemas.evidence import EvidenceCreate, EvidenceResponse
from core.security import get_current_user
import logging

router = APIRouter()
logger = logging.getLogger("uvicorn.error")

@router.post("/evidence", response_model=EvidenceResponse)
def submit_evidence(
    *,
    db: Session = Depends(get_db),
    evidence_in: EvidenceCreate,
    current_user: str = Depends(get_current_user) # Secure: Requires Token
):
    try:
        salt = uuid.uuid4().hex
        block = f"{evidence_in.source_system}{evidence_in.log_data}{salt}".encode()
        evidence_hash = hashlib.sha256(block).hexdigest()

        db_obj = AuditEntry(
            source_system=evidence_in.source_system,
            event_type=evidence_in.event_type,
            log_data=evidence_in.log_data,
            metadata_json=evidence_in.metadata,
            hash_sequence=evidence_hash,
            status="vaulted"
        )
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/vault", response_model=list[EvidenceResponse])
def get_vault(db: Session = Depends(get_db)):
    # REMOVED current_user dependency so Dashboard can sync without a login form
    return db.query(AuditEntry).all()
