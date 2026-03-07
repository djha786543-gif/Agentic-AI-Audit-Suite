# Portal End-to-End Guide

## Purpose
This is the complete operational guide for the current Agentic AI Audit Suite portal. It documents the end-to-end user journey from onboarding to evidence-backed reporting.

## Intended Audience
- Internal Auditor
- Audit Manager
- Risk Manager
- Compliance Officer
- Executive Viewer
- Platform Admin

## Portal Navigation Map
- `index.html`: Entry gateway and suite orientation.
- `app.html`: Main audit workspace and AI-assisted testing experience.
- `itgc-controls.html`: ITGC control execution and review.
- `itac-testing.html`: ITAC testing execution and review.
- `vault.html`: Evidence lineage, verification state, and traceability view.
- `governance.html`: KPI/risk/policy oversight and remediation prioritization.
- `reports.html`: Management and assurance report generation.
- `settings.html`: Source configuration and environment preferences.
- `uat.html`: Controlled UAT and release-validation operations.
- `help.html`: In-product operating guide.

## End-to-End User Journey
1. Access and orientation
- Open `index.html` and confirm advisory/operating context.
- Enter the suite via the app switcher.

2. Scope definition
- In `app.html`, define period, process, and domain scope.
- Confirm the intended test objective and output format.

3. Data readiness
- Use `settings.html` to verify source connectivity and data freshness.
- If backend endpoints are unavailable, run in documented fallback/demo mode.

4. Control execution
- Execute ITGC checks in `itgc-controls.html`.
- Execute ITAC checks in `itac-testing.html`.
- Capture exception context and evidence requirements.

5. Evidence validation
- Open `vault.html` and confirm each material finding has lineage.
- Validate verification state and integrity signals before closure.

6. Governance review
- Use `governance.html` to prioritize risks and assign ownership.
- Confirm status changes and escalation route for unresolved high-risk items.

7. Reporting and handoff
- Generate artifacts from `reports.html`.
- Provide leadership summary and follow-up tracker.

8. Release/UAT assurance
- Use `uat.html` (admin/dev workflow) for release confidence checks.
- Feed validated improvements back into weekly operating cycle.

## Role-Specific Quick Start
### Internal Auditor
- Run domain controls.
- Validate evidence.
- Draft issue narrative.

### Audit Manager
- Set risk thresholds.
- Approve escalation paths.
- Sign off report packages.

### Risk/Compliance Lead
- Review severity consistency.
- Confirm remediation ownership and due dates.

### Platform Admin
- Maintain connectors and runtime health.
- Enforce access model and operational guardrails.

### Executive Viewer
- Consume KPI/risk summaries and decision-focused report outputs.

## Output and Quality Expectations
- Findings are advisory and require professional review.
- Every high-priority finding should have evidence lineage.
- Every reporting cycle should map to owners and due dates.

## Recommended Operating Rhythm
- Daily: control execution and exception triage.
- Weekly: governance review and remediation follow-up.
- Monthly: management reporting and issue trend analysis.
- Quarterly: full assurance pack with evidence completeness checks.

## Escalation Triggers
- Repeated high-risk findings with no owner.
- Missing evidence lineage for material exceptions.
- Persistent connector/data failures impacting control coverage.
- UAT readiness below agreed threshold.
