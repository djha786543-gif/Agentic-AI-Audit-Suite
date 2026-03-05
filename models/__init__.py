"""Register all models so create_all_tables() works."""
from models.evidence_vault import AuditEntry, ExtractionRun, EvidenceVault  # noqa
from models.user import User  # noqa
from models.engagement import Engagement, EngagementRole, ControlTest, Signoff  # noqa
from models.evidence_artifact import EvidenceArtifact  # noqa
from models.methodology import ControlLibrary, TestProcedure, SamplingRule  # noqa
from models.finding import Finding, ManagementResponse, Retest  # noqa
from models.evaluation import ControlEvaluation, SODConflict  # noqa
from models.exceptions import AuditException  # noqa
# Phase 5 — Continuous Assurance & Governance
from models.governance import GovernancePolicy, ComplianceFramework, ComplianceMapping, RiskRegisterEntry  # noqa
from models.alerts import AlertRule, ComplianceAlert  # noqa
# Phase 6 — Enterprise Reporting
from models.reports import ReportDefinition, ReportRun, ReportSchedule  # noqa
