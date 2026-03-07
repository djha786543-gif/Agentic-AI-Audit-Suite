# ACAP: Agentic Continuous Assurance Platform (v6.0)

Welcome to the **Agentic Continuous Assurance Platform (ACAP)**, a fully integrated, multi-tenant enterprise audit ecosystem. It fuses a high-speed Python/PostgreSQL backend with an autonomous AI Command Center frontend. 

This platform represents a revolutionary approach to IT and Financial auditing by transitioning workflows from manual, sample-based testing to 100% automated, continuous compliance.

---

## 🏛️ The 6-Phase Architecture

ACAP is engineered on a highly secure, enterprise-grade architecture:

1. **Watcher Guards & Cryptographic Vault (Phase 1):** Background Python agents continually observe simulated ERP endpoints. They ingest raw audit logs, compute a SHA-256 hash algorithm over the exact contents, and securely write it to the Vault. Any tampering alters the hash.
2. **Zero-Trust Connectors & JWT APIs (Phase 2):** A highly secure REST API powered by FastAPI that validates every request through JWT (JSON Web Tokens) and enforces Strict Role-Based Access Control (RBAC), ensuring only authorized systems write or read data.
3. **Async PostgreSQL RLS (Phase 3):** Data isn't just stored; it's isolated. Postgres natively enforces Tenant isolation via `org_id` parameters (Row-Level Security). Multi-tenant asynchronous operations (`asyncpg`) provide unblocking enterprise data streaming logic.
4. **Autonomous AI Command Center (Phase 4):** The visual SaaS frontend where auditors command the AI. Everything executed on the screen forces async API interactions back down to Phase 3, seeding automated tests seamlessly into the database.
5. **Continuous Assurance & Governance Layer (Phase 5):** Governance policy management, compliance framework mapping, enterprise risk register, and automated threshold-based alert rules evaluated every 30 minutes by Celery. A live Governance dashboard provides real-time visibility.
6. **Enterprise Reporting (Phase 6):** On-demand and scheduled report generation for seven built-in report types (Executive Summary, Compliance Status, KPI Dashboard, Audit Findings, SOD Matrix, Risk Register, Continuous Assurance). PDF/JSON export, full run history, and a dedicated reporting page.

---

## 🚀 Quick Start Guide

### Production Database Migrations (Alembic)
For controlled enterprise releases, use Alembic migrations instead of schema re-create.

```bash
alembic upgrade head
```

Create a new migration after model changes:

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

Current enterprise hardening baseline migration:
`alembic/versions/20260307_enterprise_hardening_tables.py`

Seed enterprise IAM roles/permissions after migration:

```bash
python scripts/seed_iam.py
```

Startup schema initialization safety flags:

```env
INIT_DB_ON_STARTUP=true
RESET_DB_ON_STARTUP=false
```

Use `RESET_DB_ON_STARTUP=true` only in ephemeral local environments.

Production security guardrails:

```env
ENVIRONMENT=production
STRICT_PRODUCTION_GUARDS=true
ENABLE_HTTPS_REDIRECT=true
ENABLE_REQUEST_ID_HEADER=true
REQUEST_ID_HEADER_NAME=X-Request-ID
```

With strict guards enabled, startup fails fast if unsafe production settings are detected (for example wildcard CORS/trusted hosts, default `SECRET_KEY`, or destructive DB reset).

Prometheus metrics endpoint:

```env
ENABLE_PROMETHEUS_METRICS=true
PROMETHEUS_METRICS_PATH=/metrics
METRICS_TRACK_API_ONLY=true
```

This exposes Prometheus-compatible counters/histograms for request volume, status codes, and latency.

### Monitoring Profile (Prometheus)
Optional Docker Compose monitoring profile:

```bash
docker compose --profile monitoring up -d
```

Prometheus UI: `http://localhost:9090`
Alertmanager UI/API: `http://localhost:9093`
Grafana UI: `http://localhost:3000` (default `admin/admin`)
OTEL Collector health: `http://localhost:13133`

Config files:
- `monitoring/prometheus/prometheus.yml`
- `monitoring/prometheus/alerts.yml`
- `monitoring/prometheus/recording_rules.yml`
- `monitoring/alertmanager/alertmanager.yml`
- `monitoring/grafana/provisioning/datasources/prometheus.yml`
- `monitoring/grafana/provisioning/dashboards/dashboards.yml`
- `monitoring/grafana/dashboards/acap-overview.json`
- `monitoring/otel-collector/config.yml`

Built-in alert rules cover:
- High 5xx error rate
- High p95 latency
- Near-zero traffic detection

Alert routing defaults:
- Critical alerts -> critical webhook + email receiver
- Warning alerts -> warning webhook
- All others -> default webhook

SLO recording series (5-minute windows):
- `acap:http_requests:availability5m`
- `acap:http_requests:error_ratio5m`
- `acap:http_requests:p95_latency_seconds5m`
- `acap:http_requests:p99_latency_seconds5m`
- `acap:traces:calls_rate5m`
- `acap:traces:error_ratio5m`

Monitoring smoke CI workflow:
- `.github/workflows/monitoring-smoke.yml`

It boots the compose monitoring profile and verifies API, Prometheus, Alertmanager, and Grafana health endpoints.

OpenTelemetry tracing settings:

```env
ENABLE_OTEL_TRACING=true
OTEL_SERVICE_NAME=acap-api
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
```

Request correlation (`X-Request-ID`) is attached to both structured logs and active spans.
System logs also expose correlated `trace_id` and `span_id` values in `/api/v1/logs/system` responses.

Incident triage endpoint:
- `/api/v1/logs/system/errors/trace-groups`

This groups recent error events by `trace_id` with linked `request_id` and `span_id` values for rapid root-cause navigation.
Supported query parameters:
- `min_status` (default `400`)
- `since_minutes` (optional rolling window)
- `resource_prefix` (optional path prefix filter)
- `offset` (default `0`)
- `group_limit` (default `100`)
- `event_limit_per_group` (default `25`)
- `view` (`compact`, `ids`, or `full` preset)
- `include_event_fields` (optional comma-separated event keys)
- `q` (optional free-text search across trace_id, request_id, resource, and user)
- `q_ranked` (optional boolean relevance ranking for `q` matches)
- `trace_id_prefix` (optional trace ID prefix filter)
- `request_id_prefix` (optional request ID prefix filter)
- `sort_by` (`last_seen_at` or `error_count`)
- `sort_order` (`asc` or `desc`)

Notes:
- `view=compact` returns a minimal default event payload.
- `view=ids` returns request/span/time identifiers optimized for high-volume triage.
- `view=full` returns the full allowlisted event payload.
- If `include_event_fields` is provided, it overrides the selected `view` preset.
- If `q_ranked=true`, exact/strong ID matches are prioritized over broad text matches.

### CI Security Quality Gates
GitHub Actions workflow:
`.github/workflows/security-quality-gates.yml`

It enforces startup guardrail, observability, endpoint authorization, and core regression tests on pull requests and pushes to `main`.

### External IdP Token Validation (Azure AD / Okta)
Optional environment settings for externally-issued JWT validation:

```env
ENABLE_EXTERNAL_IDP_TOKENS=true
IDP_ISSUERS=https://login.microsoftonline.com/<tenant-id>/v2.0,https://<okta-domain>/oauth2/default
IDP_AUDIENCES=api://acap-api
IDP_JWKS_URLS=https://login.microsoftonline.com/<tenant-id>/discovery/v2.0/keys,https://<okta-domain>/oauth2/default/v1/keys
```

Optional claim mapping controls for enterprise federation:

```env
IDP_ROLE_CLAIM_KEYS=roles,groups,role
IDP_ORG_CLAIM_KEYS=org_id,tenant_id,tid
IDP_ROLE_MAPPING={"acap-audit-manager":"audit_manager","acap-admin":"system_admin"}
IDP_DEFAULT_ROLE=internal_auditor
```

These controls map external IdP claims/groups into ACAP internal roles without code changes.
See `docs/SSO_CLAIM_MAPPING.md` for operational guidance and test validation.

Optional SAML placeholders (for future SSO bridge integration):

```env
ENABLE_SAML=false
SAML_ENTITY_ID=acap-api
SAML_IDP_METADATA_URL=
SAML_IDP_METADATA_FILE=
```

### Compliance Evidence Pack Automation
Generate an auditable control evidence bundle:

```bash
make compliance-pack
```

Artifacts are generated in `artifacts/` with a manifest, SHA-256 checksum file, and zip archive.
See `docs/COMPLIANCE_EVIDENCE_PACK.md` for details.

### Operations and Incident SOPs
- `docs/OPERATIONS_RUNBOOK.md`
- `docs/INCIDENT_RESPONSE_SOP.md`
- `docs/SSO_CLAIM_MAPPING.md`
- `docs/COMPLIANCE_EVIDENCE_PACK.md`

### End-to-End User and Organization Docs
- `docs/MASTER_HANDBOOK.md`
- `docs/PORTAL_END_TO_END_GUIDE.md`
- `docs/ORGANIZATION_OPERATING_MODEL.md`
- `docs/PAGE_FLOW_REFERENCE.md`
- `docs/API_DATAFLOW_REFERENCE.md`
- `docs/ROLE_BASED_SOPS.md`
- `docs/READINESS_TEMPLATES.md`
- `docs/ACCEPTANCE_CRITERIA_MATRIX.md`

### Prerequisites
* **Python 3.10+** (Required for `asyncpg` and FastAPI compatibility)
* **Docker Desktop** (For native PostgreSQL and Redis instances)
* **Git** (For cloning the repository)
* (Optional) **Make** for running quick terminal commands.

### Dependencies (requirements.txt)
The backend is built on modern asynchronous Python frameworks:
* `fastapi==0.110.3` & `uvicorn[standard]==0.29.0` (Core API Server)
* `sqlalchemy==2.0.30` & `asyncpg==0.29.0` (Async ORM & Postgres driver)
* `celery[redis]==5.3.6` (Background Tamper-Detection Workers)
* `python-jose[cryptography]==3.3.0` (JWT Token generation)

### 1. Environment Setup
Clone the repository and install the dependencies:
```bash
git clone https://github.com/your-username/acap-agentic-audit.git
cd acap-agentic-audit
pip install -r requirements.txt
```

Rename the `.env.example` file to `.env` and configure your secure database credentials:
```bash
cp .env.example .env
```
Ensure your `POSTGRES_USER` and `POSTGRES_PASSWORD` match your desired local database settings.

### 2. Bootstrapping the Backend
Start the PostgreSQL and Redis containers using Docker Compose:
```bash
docker compose up -d
```
Generate the required Database Tables and Row-Level Security Policies:
```bash
python init_db.py
```

### 3. Launching the Application
You can launch the entire unified suite (FastAPI backend + Static Frontend) by running the native batch file or using uvicorn directly:
```bash
uvicorn main:app --reload --port 8000
```
Navigate to the Gateway: 👉 **[http://localhost:8000/](http://localhost:8000/)**

### 4. Simulating Live Traffic
To start streaming immutable logs to the vault in the background, open a separate terminal and run the Watcher Agent:
```bash
python watcher_agent.py
```

---

## 🕹️ Website & Feature Guide

The platform interface is broken down into three major pages:

### 1. The Gateway Portal (`index.html`)
Your entry point to the suite. Designed to demonstrate architectural value to executives and investors.
* **Hero Section:** High-level overview of the autonomous SOC testing premise.
* **Status Pill:** A live indicator confirming the async FastAPI backend is broadcasting successfully.
* **Navigation Links:** Instant traversal to the "Live Vault" or the "SaaS Command Center".

### 2. The Live Data Vault (`vault.html`)
The cryptographically sealed ledger. It queries the backend API (`/api/v1/audit/vault`) every few seconds to refresh the data grid automatically.
* **SHA-256 Hashes:** Displays the truncated cryptographic seal of every event ingested by Watcher Guards.
* **Tamper Detection:** If altered data is detected, the UI instantly flips the row to a RED 'Tampered' alert status.
* **Advanced Filters:** Filter incoming raw logs by Date, Source System (Active Directory, FileSystem, etc.), or specific hash strings.

### 3. The SaaS Command Center (`app.html`)
The absolute core of the Phase 4 integrations. This is where auditors trigger tests and extract outputs.
* **AI Rule Modules:** Includes dedicated testing clusters like Segregation of Duties (SOD), Change Management, and Financial Forensics.
* **Live API Sync:** Clicking "Run Scan" locally renders the results while simultaneously transmitting JSON webhooks into the Python backend (`/api/v1/evaluation/controls`), permanently archiving the executed test in PostgreSQL.
* **KPI Dashboard:** Features dynamic data metrics mapping to live tests.

### 4. Governance & Continuous Assurance (`governance.html`)
The Phase 5 governance command center for auditors and compliance officers.
* **Live Assurance KPIs:** Pass rate, failed controls, open exceptions, SOD conflicts, and open alerts auto-refreshed every 30 seconds.
* **Compliance Alerts:** View active alerts raised automatically by the Celery monitoring sweep or manually by auditors.
* **Governance Policies:** Full CRUD interface for organizational governance policies with status, version, and owner tracking.
* **Compliance Frameworks:** Register and manage compliance standards (SOX, ISO 27001, COBIT 2019, etc.) and map controls to framework requirements.
* **Risk Register:** Enterprise risk register with automated risk scoring (likelihood × impact), risk ratings, and treatment classification.
* **Alert Rules:** Configure threshold-based alert rules evaluated every 30 minutes against live DB metrics.

### 5. Enterprise Reporting (`reports.html`)
The Phase 6 reporting hub for generating and exporting board-ready audit deliverables.
* **Quick Generate Cards:** One-click report generation for seven built-in types: Executive Summary, Compliance Status, KPI Dashboard, Audit Findings, SOD Matrix, Risk Register, and Continuous Assurance.
* **Interactive Viewer:** Modal report viewer with KPI mini-cards for instant insights without opening a file.
* **PDF Export:** jsPDF-powered export with ACAP branding, KPI tables, compliance coverage tables, and official standard references (SOX 404, PCAOB AS 2201, COSO 2013).
* **JSON Export:** Machine-readable full report payload for integration with external GRC tools.
* **Run History:** Complete audit trail of all generated reports with replay capability.

### 📑 Generating Audit Deliverables (SOX Compliant)
Automated testing requires automated workpapers. Using the exporters inside the **Command Center**:
1. Choose an AI Module (e.g., Segregation of Duties).
2. Execute the AI Control Evaluation.
3. Scroll to the "Workpaper Generation" section.
4. **Word (.docx):** Downloads a natively editable Microsoft Word document utilizing a `docx.js` buffer.
5. **PDF Extractor:** Uses `jsPDF` to lock the AI findings into un-editable, Board-ready formats utilizing official standard PCAOB AS 2201 audit opinions.
6. **System Spreadsheets (.csv):** Standard downloads format perfectly into Excel for data analysis.

---

## 🛡️ License & Contributions
This project is proprietary and intended for Enterprise IT Audit Assurance. 
Please ensure no production secrets or real audit evidence are committed to public repositories.

Repository legal controls:
- `LICENSE` - Proprietary "All Rights Reserved" license terms.
- `NOTICE` - Copyright and unauthorized-use notice.
- `.github/CODEOWNERS` - Ownership enforcement for review routing.

Unauthorized copying, redistribution, derivative reuse, or commercial exploitation is prohibited without prior written authorization from the repository owner.
