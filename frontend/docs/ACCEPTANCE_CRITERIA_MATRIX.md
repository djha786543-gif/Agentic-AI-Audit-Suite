# Operational Acceptance Criteria Matrix

## Purpose
Define objective acceptance criteria for core portal workflows and organizational readiness.

## Scale
- `Pass`: criterion fully met.
- `Conditional`: partially met; remediation required with due date.
- `Fail`: unmet; release or signoff should be blocked.

## Matrix
| Area | Criterion | Evidence Source | Owner | Status Rule |
|---|---|---|---|---|
| Access & Roles | Required users mapped to approved roles | Auth/RBAC records | System Admin | Fail if any critical role unmapped |
| Data Connectivity | Primary connectors tested successfully | Settings validation + logs | System Admin | Fail if primary source unavailable |
| ITGC Execution | Scheduled scope completed | ITGC outputs | Internal Auditor | Conditional if completion < 100% |
| ITAC Execution | Scheduled scope completed | ITAC outputs | Internal Auditor | Conditional if completion < 100% |
| Evidence Integrity | Material findings have evidence lineage and verification state | Vault + evidence metadata | Compliance Officer | Fail if missing lineage on critical findings |
| Workflow Governance | High/critical findings assigned owner and due date | Governance records | Audit Manager | Fail if unowned critical findings exist |
| Risk Oversight | Risk prioritization reviewed and updated | Governance dashboard | Risk Manager | Conditional if review skipped |
| Reporting | Monthly/quarterly report package generated and reviewed | Reports artifacts | Audit Manager | Fail if report not generated |
| UAT Readiness | UAT baseline checks pass for release window | UAT outputs | Admin/Developer | Fail if readiness below threshold |
| Incident Preparedness | Incident SOP validated and team aware of escalation path | SOP review evidence | Platform Ops | Conditional if training incomplete |

## Minimum Go/No-Go Rule
- `No-Go` if any `Fail` in: Access, Data Connectivity, Evidence Integrity, UAT Readiness.
- `Go with Conditions` if only `Conditional` items exist and mitigation dates are approved.
- `Go` when all criteria are `Pass`.

## Signoff Block
- Cycle: <period>
- Reviewed by: <name/role>
- Decision: <Go | Go with Conditions | No-Go>
- Conditions/Actions: <list>
- Date: <timestamp>
