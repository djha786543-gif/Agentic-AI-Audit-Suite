from db.session import engine
from db.base import Base
import models  # This will trigger the __init__.py which imports all models

import re
from sqlalchemy import text

# Whitelist of tables that receive Row-Level Security policies.
# Table names must match this pattern to prevent any unexpected SQL injection.
_TABLE_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,62}$")

_RLS_TABLES = [
    "users", "audit_vault", "extraction_runs",
    "engagements", "engagement_roles", "control_tests", "signoffs",
    "evidence_artifacts",
    "control_library", "test_procedures", "sampling_rules",
    "findings", "management_responses", "retests",
    "control_evaluations", "sod_conflicts",
    "audit_exceptions",
    # Phase 5 — Continuous Assurance & Governance
    "governance_policies", "compliance_frameworks", "compliance_mappings",
    "risk_register", "alert_rules", "compliance_alerts",
    # Phase 6 — Enterprise Reporting
    "report_definitions", "report_runs", "report_schedules",
]


def _apply_rls(conn, table: str) -> None:
    """Apply RLS enable + tenant isolation policy to a single table."""
    # Validate table name against the hardcoded whitelist and safe-name pattern.
    if table not in _RLS_TABLES:
        raise ValueError(f"Table '{table}' is not in the RLS whitelist.")
    if not _TABLE_NAME_PATTERN.match(table):
        raise ValueError(f"Table name '{table}' contains invalid characters.")

    # Table names cannot be parameterised in DDL statements; the whitelist
    # check above ensures only known-safe names reach this point.
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


def init_db():
    print("🔄 Initializing Audit Vault Schema...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        for table in _RLS_TABLES:
            _apply_rls(conn, table)

    print("✅ Tables Created with RLS Enforced for all tables including evaluations and exceptions")


if __name__ == "__main__":
    init_db()

