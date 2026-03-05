# ACAP Implementation Guide

> **Agentic Continuous Assurance Platform** — 4-Phase Build Roadmap

This guide describes each build phase, the files involved, and how to verify
each phase is working correctly.

---

## Phase 1 — Vault + SHA-256 Integrity ✅ Complete

**Goal:** Immutable, hash-verified evidence vault with Celery-powered tamper detection.

### Files
| File | Purpose |
|------|---------|
| `models/evidence_vault.py` | `AuditEntry` + `ExtractionRun` ORM models |
| `vault/writer.py` | Chain-of-custody write: ledger first → hash → evidence |
| `schemas/evidence.py` | Pydantic request/response shapes |
| `core/celery_app.py` | Celery + Beat scheduler setup |
| `worker/integrity.py` | Periodic hash re-verification task (every 60 min) |
| `worker/tasks.py` | `execute_control_test` + `run_watcher_cycle` tasks |
| `docker-compose.yml` | PostgreSQL, Redis, Celery worker, Beat, API |
| `init_db.py` | Creates all tables + Row-Level Security policies |
| `main.py` | FastAPI app entry point serving API + static frontend |

### Verify
1. `docker compose up -d` — all 5 services healthy
2. `python watcher_agent.py` — streams evidence to vault
3. `GET /api/v1/audit/vault` — returns records with `content_hash` + `hash_verified=true`
4. `GET /api/v1/audit/vault/summary` — shows counts
5. `GET /api/v1/audit/runs` — extraction run audit trail

---

## Phase 2 — Connector Framework + JWT/RBAC ✅ Complete

**Goal:** Pluggable connector architecture, JWT-protected endpoints, and role-based
access control so external auditors get read-only scoped tokens while connector
service accounts have their own role.

### Files
| File | Purpose |
|------|---------|
| `connectors/base.py` | Abstract `BaseConnector` — every connector must implement `fetch()` and `health_check()` |
| `connectors/azure_ad.py` | Microsoft Graph connector (mock mode by default, real mode when `AZURE_*` env vars are set) |
| `auth/__init__.py` | Package marker |
| `auth/rbac.py` | `UserRole` enum + `require_role()` FastAPI dependency |
| `auth/context.py` | `AuthContext` dataclass — carries `username`, `role`, `org_id` from JWT claims |
| `core/security.py` | `create_access_token`, `get_current_user`, `get_auth_context` |
| `api/v1/endpoints/auth.py` | `POST /auth/login` — returns JWT with role + org_id embedded |
| `api/v1/endpoints/connectors.py` | `GET /connectors/health`, `GET /connectors/{connector_id}/health` |
| `models/user.py` | `User` model with `role` field |

### Roles
| Role | Token claim value | Access |
|------|-------------------|--------|
| `INTERNAL_AUDITOR` | `internal_auditor` | Full read + write |
| `EXTERNAL_AUDITOR` | `external_auditor` | Read-only vault + evaluation results |
| `CONNECTOR_SERVICE` | `connector_service` | Write evidence, read own runs |

### Environment Variables (Phase 2 additions)
```
# .env additions for Azure AD connector (optional — mock mode if absent)
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret
```

### Verify
1. `POST /api/v1/auth/login` with `username=admin&password=Audit123!` — returns JWT
2. Decode JWT — check `role` and `org_id` claims present
3. `GET /api/v1/connectors/health` — lists all registered connectors with status
4. `GET /api/v1/connectors/azure_ad/health` — returns mock connector health
5. `POST /api/v1/audit/evidence` without token — returns 401
6. `POST /api/v1/audit/evidence` with `external_auditor` token — returns 403 (write blocked)

---

## Phase 3 — Multi-Tenancy + PostgreSQL RLS + Async DB

**Goal:** `org_id` on every table, PostgreSQL Row-Level Security enforced at DB layer,
async SQLAlchemy sessions, and dynamic tenant resolution from JWT context.

### Key Behaviours
- Every table has an `org_id` column
- `init_db.py` creates `tenant_isolation_policy` for every table using
  `current_setting('app.current_tenant', true)`
- `db/async_session.py` sets `app.current_tenant` from the authenticated user's
  `org_id` on every request
- Integrity verifier Celery task fully wired — re-verifies hashes every 60 min

### Files
| File | Purpose |
|------|---------|
| `db/async_session.py` | Async session factory + `get_async_db` dependency |
| `db/session.py` | Sync session factory for Celery workers |
| `init_db.py` | Applies RLS to all tables including evaluation + exception tables |

### Verify
1. `GET /api/v1/audit/vault` as `org_a` token — only sees org_a records
2. `GET /api/v1/audit/vault` as `org_b` token — only sees org_b records

---

## Phase 4 — Control Evaluation + SOD Matrix + Exception Workflow + Audit Packages

**Goal:** Parameterised ITGC test engine, terminated user access test, SOD conflict
detection, exception lifecycle (open → acknowledge → remediate → accept), and
sealed audit packages.

### Engines
| Module | Tests |
|--------|-------|
| `engine/sod.py` | 40+ SOD conflict rules across AP, AR, GL, Payroll, IT, Procurement |
| `engine/access.py` | Terminated users, dormant accounts, missing MFA, excessive privilege, overdue reviews |
| `engine/change.py` | Change management controls |
| `engine/operations.py` | Operations / availability controls |
| `engine/itac.py` | Three-way match, duplicate payments, approval bypass, calculation accuracy |
| `engine/runner.py` | Master orchestrator — aggregates all engines, computes risk score |
| `engine/parser.py` | File parser — CSV / Excel / JSON / SAP TXT |

### API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/engine/analyze` | Upload file → full multi-engine audit |
| `POST` | `/api/v1/engine/analyze/sod` | SoD-only with explicit roles payload |
| `GET` | `/api/v1/engine/health` | Confirms all engine modules loaded |
| `GET` | `/api/v1/evaluation/controls` | List control evaluations |
| `POST` | `/api/v1/evaluation/controls` | Record a control evaluation |
| `GET` | `/api/v1/evaluation/sod` | List SOD conflicts |
| `POST` | `/api/v1/evaluation/sod` | Record a SOD conflict |
| `GET` | `/api/v1/evaluation/exceptions` | List audit exceptions |
| `POST` | `/api/v1/evaluation/exceptions` | Create an exception |
| `PATCH` | `/api/v1/evaluation/exceptions/{id}/transition` | Transition exception state |
| `GET` | `/api/v1/engagement/` | List audit engagements |
| `POST` | `/api/v1/engagement/` | Create engagement |
| `POST` | `/api/v1/engagement/{id}/signoff` | Digital sign-off |

### Exception Lifecycle
```
open → acknowledged → remediation_in_progress → remediated → closed
                    ↘ accepted_risk → closed
```

### Verify
1. `POST /api/v1/engine/analyze` with sample CSV — returns findings JSON
2. `POST /api/v1/evaluation/sod` — creates SOD conflict record
3. `GET /api/v1/evaluation/exceptions` — lists open exceptions
4. `PATCH /api/v1/evaluation/exceptions/{id}/transition` body `{"new_state":"acknowledged"}` — advances lifecycle

---

## Phase 5 — Continuous Assurance & Governance Layer

**Goal:** Governance policy management, compliance framework mapping, enterprise risk register,
threshold-based alert rules evaluated automatically by Celery, and a live Governance dashboard.

### New Models
| File | Models |
|------|--------|
| `models/governance.py` | `GovernancePolicy`, `ComplianceFramework`, `ComplianceMapping`, `RiskRegisterEntry` |
| `models/alerts.py` | `AlertRule`, `ComplianceAlert` |

### New Schemas
| File | Schemas |
|------|---------|
| `schemas/governance.py` | Policy, Framework, Mapping, Risk create/response shapes |
| `schemas/alerts.py` | `AlertRuleCreate/Response`, `ComplianceAlertCreate/Response`, `AlertAcknowledge`, `AlertResolve` |

### API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/governance/policies` | List governance policies |
| `POST` | `/api/v1/governance/policies` | Create a governance policy |
| `GET` | `/api/v1/governance/policies/{policy_id}` | Get a single policy |
| `GET` | `/api/v1/governance/frameworks` | List compliance frameworks |
| `POST` | `/api/v1/governance/frameworks` | Register a framework |
| `GET` | `/api/v1/governance/mappings` | List compliance mappings |
| `POST` | `/api/v1/governance/mappings` | Create a control↔framework mapping |
| `GET` | `/api/v1/governance/risks` | List risk register entries |
| `POST` | `/api/v1/governance/risks` | Add risk register entry |
| `GET` | `/api/v1/governance/risks/{risk_id}` | Get a single risk |
| `GET` | `/api/v1/alerts/rules` | List alert rules |
| `POST` | `/api/v1/alerts/rules` | Create an alert rule |
| `GET` | `/api/v1/alerts/` | List compliance alerts |
| `POST` | `/api/v1/alerts/` | Raise a manual alert |
| `PATCH` | `/api/v1/alerts/{id}/acknowledge` | Acknowledge an alert |
| `PATCH` | `/api/v1/alerts/{id}/resolve` | Resolve an alert |

### Continuous Monitoring Worker
`worker/continuous_monitoring.py` — Celery task `run_monitoring_sweep` evaluates all
active `AlertRule` records every **30 minutes** (Celery Beat schedule).

Supported metric names:
- `failed_controls_count`
- `open_exceptions_count`
- `critical_findings_count`
- `sod_conflicts_count`
- `open_alerts_count`

Supported operators: `gte`, `gt`, `lte`, `lt`, `eq`

### Frontend
`frontend/governance.html` — Full Governance & Continuous Assurance dashboard:
- Live KPI refresh (30 s interval)
- Compliance Alerts management
- Governance Policy CRUD
- Compliance Framework registration
- Risk Register CRUD
- Alert Rule configuration

### Verify
1. `POST /api/v1/governance/policies` — creates policy
2. `POST /api/v1/governance/risks` — computes risk_score + risk_rating automatically
3. `POST /api/v1/alerts/rules` body `{"rule_id":"R1","name":"x","metric":"failed_controls_count","operator":"gte","threshold":1}` — creates rule
4. `GET /api/v1/alerts/` — returns alerts raised by the monitoring sweep
5. Open `http://localhost:8000/governance.html` — live dashboard

---

## Phase 6 — Enterprise Reporting

**Goal:** On-demand and scheduled report generation with PDF/JSON export, executive
dashboard aggregation, compliance status by framework, and a full Report Run history.

### New Models
| File | Models |
|------|--------|
| `models/reports.py` | `ReportDefinition`, `ReportRun`, `ReportSchedule` |

### New Schemas
| File | Schemas |
|------|---------|
| `schemas/reports.py` | `ReportDefinitionCreate/Response`, `ReportRunRequest/Response`, `ReportScheduleCreate/Response`, `KPISummary`, `ComplianceStatusSummary`, `ExecutiveDashboard` |

### API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/reports/dashboard` | Full executive dashboard (KPIs + compliance + alerts + risks) |
| `GET` | `/api/v1/reports/kpis` | Standalone KPI snapshot |
| `GET` | `/api/v1/reports/definitions` | List saved report definitions |
| `POST` | `/api/v1/reports/definitions` | Create a report definition |
| `GET` | `/api/v1/reports/runs` | List all report runs |
| `POST` | `/api/v1/reports/runs` | Trigger on-demand report generation |
| `GET` | `/api/v1/reports/runs/{run_id}` | Retrieve a specific report run |
| `GET` | `/api/v1/reports/schedules` | List report schedules |
| `POST` | `/api/v1/reports/schedules` | Create a recurring report schedule |

### Built-in Report Types
| Type | Description |
|------|-------------|
| `executive_summary` | KPIs + compliance framework coverage + standard references |
| `compliance_status` | Coverage % per active framework |
| `kpi_dashboard` | All KPI metrics from live DB state |
| `audit_findings` | All findings with severity, status, and control references |
| `sod_matrix` | All SOD conflicts with resolution status |
| `risk_register` | Full risk register with scores and ratings |
| `continuous_assurance` | KPIs + last 50 compliance alerts |

### Frontend
`frontend/reports.html` — Enterprise Reporting page:
- Quick Generate cards for every built-in report type
- Interactive report viewer modal with KPI mini-cards
- PDF export (jsPDF + autotable) with ACAP branding and standard references
- JSON export
- Full run history table with replay viewer

### Verify
1. `GET /api/v1/reports/dashboard` — returns `ExecutiveDashboard` payload
2. `POST /api/v1/reports/runs` body `{"report_type":"executive_summary","name":"Q1 2026"}` — generates report
3. `GET /api/v1/reports/runs` — lists all generated reports
4. Open `http://localhost:8000/reports.html` — click any Quick Generate card, view results, export PDF

---


```bash
# 1. Copy and configure environment
cp .env.example .env
# Edit .env with your database credentials and SECRET_KEY

# 2. Start Docker services (PostgreSQL, Redis, Celery worker + beat)
docker compose up -d

# 3. Initialise database schema + RLS policies
python init_db.py

# 4. Start the API + frontend server
uvicorn main:app --reload --port 8000

# 5. (Optional) Stream live evidence
python watcher_agent.py
```

Navigate to **[http://localhost:8000/](http://localhost:8000/)** for the dashboard.

API docs: **[http://localhost:8000/docs](http://localhost:8000/docs)**

---

## Security Notes

- Never commit `.env` to version control
- Rotate `SECRET_KEY` before any production deployment
- Use short-lived tokens (default: 60 min) for external auditors
- RLS policies prevent cross-tenant data leakage even if application code has bugs
- All SHA-256 hashes are computed server-side — clients cannot influence the hash
