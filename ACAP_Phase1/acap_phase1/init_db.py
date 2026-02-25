from db.session import engine
from db.base_class import Base
from models.user import User
from models.evidence_vault import AuditEntry

def init_db():
    print("?? Initializing Audit Vault Schema...")
    Base.metadata.create_all(bind=engine)
    print("? Tables Created: [users, audit_vault, extraction_runs]")

if __name__ == "__main__":
    init_db()
