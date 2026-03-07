# Page Flow Reference

## Purpose
Map each portal page to user actions, inputs, outputs, and downstream dependencies.

## `index.html`
- Role: Suite entry and navigation orientation.
- Input: user navigation intent.
- Output: page routing to functional modules.

## `app.html`
- Role: Main audit workspace.
- Input: scope selections, file/source inputs, policy parameters, user prompts.
- Output: control results, AI-assisted summaries, downstream findings context.
- Dependencies: ITGC/ITAC pages, reports, governance, vault.

## `itgc-controls.html`
- Role: ITGC testing and review.
- Input: access/change/operations control datasets.
- Output: control status and exception candidates.
- Dependencies: vault evidence verification, governance prioritization.

## `itac-testing.html`
- Role: ITAC testing and review.
- Input: application transaction/control data.
- Output: test outcomes and application-level exceptions.
- Dependencies: vault and reporting.

## `vault.html`
- Role: evidence traceability and verification visibility.
- Input: audit/evidence records, integrity metadata.
- Output: verification state, lineage context, audit trail support.

## `governance.html`
- Role: risk and policy oversight.
- Input: KPI, alerts, risks, policy/framework entries.
- Output: prioritized risk and ownership actions.

## `reports.html`
- Role: reporting and export center.
- Input: findings, risks, KPI snapshots, review package requests.
- Output: management-ready report artifacts.

## `settings.html`
- Role: platform and source configuration.
- Input: connector and environment settings.
- Output: validated connectivity baseline for execution pages.

## `uat.html`
- Role: controlled test/release validation.
- Input: run params, compare requests, autopilot controls.
- Output: readiness signal and validation artifacts.

## `help.html`
- Role: user-facing guide and operational documentation.
- Input: search, section navigation.
- Output: documented procedures and references.

## Recommended Cross-Page Flow
1. Settings -> App
2. App -> ITGC/ITAC
3. ITGC/ITAC -> Vault
4. Vault -> Governance
5. Governance -> Reports
6. Reports -> UAT (release validation)
