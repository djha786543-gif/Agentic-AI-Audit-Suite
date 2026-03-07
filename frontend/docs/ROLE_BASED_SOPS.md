# Role-Based SOP Checklists

## Purpose
Provide operational checklists by role so teams can execute portal workflows consistently and with clear accountability.

## How to Use
- Use the checklists as runbooks during daily operations.
- Mark completion evidence in your internal tracker.
- Escalate blockers using your incident and governance procedures.

## System Admin SOP
### Daily
- Confirm API health and readiness endpoints are green.
- Confirm database and Redis availability.
- Review system log error groups for new critical patterns.

### Weekly
- Review user/role assignments for least-privilege alignment.
- Verify monitoring dashboards and alert routes are operational.
- Validate backup/restore script readiness and storage capacity.

### Monthly
- Rotate sensitive secrets according to policy.
- Review dependency/security scan outputs and remediation status.
- Validate workflow and auth configuration against current org policy.

## Internal Auditor SOP
### Per Audit Cycle
- Define scope (period, process, control domains).
- Execute ITGC and ITAC workflows.
- Review exception findings and attach evidence references.
- Confirm each material finding has verifiable lineage.

### Before Reporting
- Validate finding severity rationale.
- Confirm remediation owners and target dates are assigned.
- Ensure unresolved critical findings are explicitly flagged.

## Audit Manager SOP
### Weekly Governance Review
- Review open exceptions and overdue actions.
- Validate risk prioritization and reassignment where needed.
- Confirm report narrative aligns with current risk posture.

### Signoff Criteria
- Required controls executed for agreed scope.
- Evidence available for all material findings.
- Management responses captured for open high/critical issues.

## Risk Manager SOP
### Weekly
- Review risk register deltas and trend direction.
- Validate likelihood/impact consistency with control outcomes.
- Escalate concentrated systemic risk patterns.

### Monthly
- Review mitigation plan quality and closure confidence.
- Confirm top risks reflected in leadership reporting.

## Compliance Officer SOP
### Audit Evidence Quality
- Verify evidence metadata completeness (audit/control/timestamp/hash/status).
- Confirm immutable trail records for key workflow events.
- Validate policy/framework mappings are current.

### External Review Preparation
- Build compliance pack and verify checksums.
- Confirm report package consistency with governance records.

## Executive Viewer SOP
### Monthly Readout
- Review KPI/risk trends and top unresolved issues.
- Confirm remediation throughput against timeline expectations.
- Approve directional decisions and escalate blockers.

## UAT / Admin-Developer SOP
- Run controlled UAT in `uat.html`.
- Compare latest run to baseline before release.
- Block deployment when readiness is below agreed threshold.
- Capture run output and link to release evidence.
