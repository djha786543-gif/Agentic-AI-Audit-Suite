from db.session import engine
from db.base import Base
from models.user import User
from models.evidence_vault import AuditEntry

from sqlalchemy import text

from models.evaluation import ControlEvaluation, SODConflict
from models.exceptions import AuditException

def init_db():
    print("?? Initializing Audit Vault Schema...")
    Base.metadata.create_all(bind=engine)
    
    with engine.begin() as conn:
        tables_to_rls = [
            "users", "audit_vault", "extraction_runs", 
            "control_evaluations", "sod_conflicts", "audit_exceptions"
        ]
        for table in tables_to_rls:
            conn.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;"))
            conn.execute(text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;"))
            conn.execute(text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table};"))
            
            conn.execute(text(f"""
                CREATE POLICY tenant_isolation_policy ON {table}
                AS PERMISSIVE FOR ALL
                USING (org_id = current_setting('app.current_tenant', true))
                WITH CHECK (org_id = current_setting('app.current_tenant', true));
            """))
            
    print("? Tables Created with RLS Enforced for Phase 1-4")

if __name__ == "__main__":
    init_db()
