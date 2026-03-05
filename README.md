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
