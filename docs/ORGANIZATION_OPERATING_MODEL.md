# Organization Operating Model

## Objective
Define how an organization should run the portal in a repeatable, controlled, and auditable way.

## Governance Structure
- Program Sponsor: accountable for strategic outcomes.
- Audit Manager: accountable for control scope and reporting quality.
- Risk Manager: accountable for risk prioritization and treatment decisions.
- Compliance Officer: accountable for standards alignment and evidence integrity.
- Platform Admin: accountable for platform operations and environment controls.

## RACI Snapshot
- Scope design: Audit Manager (A), Auditor (R), Risk/Compliance (C), Executive (I)
- Control execution: Auditor (R), Audit Manager (A)
- Evidence validation: Auditor (R), Compliance (A)
- Risk triage: Risk Manager (A), Audit Manager (R)
- Reporting signoff: Audit Manager (R), Sponsor (A)
- Runtime operations: Platform Admin (A/R)

## Standard Cadence
### Daily
- Run scoped controls.
- Review new exceptions.
- Validate evidence availability.

### Weekly
- Review top risks and overdue items.
- Confirm remediation owners and status updates.

### Monthly
- Produce leadership report pack.
- Review trend lines and residual risk movement.

### Quarterly
- Conduct full readiness/attestation cycle.
- Run UAT checks and operating model retrospective.

## Decision Controls
- Severity thresholds must be pre-agreed.
- High/critical findings require owner and due date before closure.
- Report publication requires manager signoff.
- Evidence gaps block closure for material findings.

## Minimum Data and Evidence Standards
- Required fields must be complete for tested controls.
- Timestamp and source traceability must be present.
- Evidence verification status must be explicit.

## UAT and Release Model
- UAT is admin/dev controlled.
- Release requires acceptable run health and no critical unresolved blockers.
- Post-release validation is required in first business cycle.

## Documentation Discipline
- Keep `help.html` as user entry point.
- Keep `/docs` as deep-reference source of truth.
- Update docs after workflow, endpoint, or governance changes.
