from db.session import engine
from db.base import Base
import models  # This will trigger the __init__.py which imports all models

from sqlalchemy import text

def init_db():
    print("?? Initializing Audit Vault Schema...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    with engine.begin() as conn:
        tables = [
            "users", "audit_vault", "extraction_runs",
            "engagements", "engagement_roles", "control_tests", "signoffs",
            "evidence_artifacts",
            "control_library", "test_procedures", "sampling_rules",
            "findings", "management_responses", "retests"
        ]
        for table in tables:
            conn.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;"))
            conn.execute(text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;"))
            conn.execute(text(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table};"))
            
            # The policy uses current_setting('app.current_tenant', true)
            # The 'true' argument means it won't throw an error if missing (returns null instead).
            conn.execute(text(f"""
                CREATE POLICY tenant_isolation_policy ON {table}
                AS PERMISSIVE FOR ALL
                USING (org_id = current_setting('app.current_tenant', true))
                WITH CHECK (org_id = current_setting('app.current_tenant', true));
            """))
            
    print("? Tables Created with RLS Enforced: [users, audit_vault, extraction_runs]")

if __name__ == "__main__":
    init_db()
