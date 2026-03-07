# ACAP Master Handbook

## Document Control
- Product: Agentic Continuous Assurance Platform (ACAP)
- Scope: End-to-end operational handbook for portal usage, governance, controls, and signoff
- Audience: Executives, Audit Managers, Risk/Compliance Leads, Auditors, Platform Admins
- Source References: `help.html` and all `/docs` operational guides

## How to Use This Handbook
1. Start with the Executive Summary for decision context.
2. Use the Operating Model and RACI to assign responsibilities.
3. Follow the End-to-End Flow for day-to-day execution.
4. Apply SOP checklists by role.
5. Use templates and acceptance matrix for formal signoff.

---

## 1. Executive Summary
ACAP provides a multi-page audit portal that supports ITGC/ITAC execution, evidence lineage, governance oversight, and reporting outputs in a single operational flow. The platform is designed to reduce cycle time, standardize control testing, and improve traceability from finding to remediation.

Primary outcomes:
- Faster control execution through guided workflows.
- Stronger evidence traceability via vault and integrity status.
- More consistent governance decisions with KPI/risk views.
- Repeatable reporting and readiness cycles.

---

## 2. Portal Architecture and Navigation
### Core Pages
- `index.html`: Entry point and orientation.
- `app.html`: Main audit workspace and AI-assisted orchestration surface.
- `itgc-controls.html`: ITGC test execution.
- `itac-testing.html`: ITAC test execution.
- `vault.html`: Evidence lineage and verification.
- `governance.html`: KPI/risk/policy oversight.
- `reports.html`: Report generation and exports.
- `settings.html`: Source and configuration controls.
- `uat.html`: Controlled release/UAT operations.
- `help.html`: In-product operational guide.

### Recommended Navigation Sequence
1. Settings
2. App
3. ITGC/ITAC
4. Vault
5. Governance
6. Reports
7. UAT

---

## 3. Organization Operating Model
### Governance Roles
- Program Sponsor
- Audit Manager
- Internal Auditor
- Risk Manager
- Compliance Officer
- Platform Admin
- Executive Viewer

### RACI Summary
- Scope and control strategy: Audit Manager (A), Auditor (R)
- Daily execution and evidence: Auditor (R), Compliance (C)
- Risk prioritization: Risk Manager (A)
- Runtime/availability: Platform Admin (A/R)
- Report signoff: Audit Manager (R), Sponsor (A)

### Standard Cadence
- Daily: execute controls, triage exceptions, validate evidence.
- Weekly: governance and remediation review.
- Monthly: leadership reporting and trend review.
- Quarterly: full assurance package and release/UAT checkpoint.

---

## 4. End-to-End Operational Flow
### Phase A: Scope and Data Readiness
- Confirm period/process/domain scope.
- Validate connectors and source accessibility.
- Confirm role assignments and operating boundaries.

### Phase B: Control Execution
- Run ITGC workflows.
- Run ITAC workflows.
- Capture initial exceptions and classify severity.

### Phase C: Evidence and Traceability
- Validate each material finding has evidence lineage.
- Confirm verification status and timestamp integrity.
- Record missing evidence as blocker conditions.

### Phase D: Governance and Action
- Prioritize findings by risk and impact.
- Assign owner, due date, and response plan.
- Escalate unresolved high/critical items.

### Phase E: Reporting and Signoff
- Generate management report package.
- Attach evidence artifacts/checksums as needed.
- Complete acceptance matrix and signoff decision.

---

## 5. Role-Based SOPs (Quick Reference)
### System Admin
- Ensure API/readiness health, connector status, and logging visibility.
- Maintain runtime guardrails and environment hygiene.

### Internal Auditor
- Execute tests, validate exceptions, and attach evidence context.
- Ensure material issues include decision rationale.

### Audit Manager
- Confirm scope completion and quality of remediation ownership.
- Approve reporting narrative and escalation outcomes.

### Risk Manager
- Validate risk prioritization and trend direction.
- Ensure treatment decisions align with control outcomes.

### Compliance Officer
- Verify evidence completeness and immutable trail quality.
- Prepare compliance pack for external/internal review.

### Executive Viewer
- Review KPI/risk summaries and decision recommendations.
- Approve directional actions and accountability path.

---

## 6. Readiness Templates
### Day-0 Onboarding
- Users/roles provisioned
- Sources connected and tested
- Pilot cycle completed
- Initial evidence traceability validated

### Day-30 Stabilization
- Weekly governance rhythm in place
- Ownership and due-date discipline visible
- Reporting accepted by stakeholder audience

### Quarterly Assurance
- Scope refresh complete
- Full execution + governance + reporting cycle complete
- Compliance evidence package generated and verified

---

## 7. Acceptance Criteria Matrix (Go/No-Go)
Critical gates that must pass:
- Access and role alignment
- Data connectivity for in-scope sources
- Evidence integrity on material findings
- UAT readiness for release windows

Decision model:
- No-Go: any critical gate fails.
- Go with Conditions: no critical failures, but conditional items exist with approved due dates.
- Go: all criteria pass.

---

## 8. Risk and Escalation Guidance
Escalate immediately when:
- High/critical findings are unowned.
- Material findings lack evidence lineage.
- Connector failures block required controls.
- UAT readiness falls below agreed threshold.

Use incident and operations runbooks for containment, communications, and recovery.

---

## 9. Evidence and Reporting Package Standards
A complete package should include:
- Executive summary and KPI/risk posture
- Finding details and remediation tracker
- Evidence references and verification status
- Compliance artifact bundle with manifest/checksum

Optional but recommended:
- UAT comparison output for release windows
- System log/trace references for critical incidents

---

## 10. Supporting Documents Index
- `docs/PORTAL_END_TO_END_GUIDE.md`
- `docs/ORGANIZATION_OPERATING_MODEL.md`
- `docs/PAGE_FLOW_REFERENCE.md`
- `docs/API_DATAFLOW_REFERENCE.md`
- `docs/ROLE_BASED_SOPS.md`
- `docs/READINESS_TEMPLATES.md`
- `docs/ACCEPTANCE_CRITERIA_MATRIX.md`
- `docs/OPERATIONS_RUNBOOK.md`
- `docs/INCIDENT_RESPONSE_SOP.md`
- `docs/SSO_CLAIM_MAPPING.md`
- `docs/COMPLIANCE_EVIDENCE_PACK.md`

---

## 11. Formal Signoff Block
- Cycle: `<period>`
- Scope: `<entities/processes/domains>`
- Reviewer: `<name/role>`
- Decision: `<Go | Go with Conditions | No-Go>`
- Conditions/Actions: `<details>`
- Approved Date: `<timestamp>`
- Next Review Date: `<timestamp>`
