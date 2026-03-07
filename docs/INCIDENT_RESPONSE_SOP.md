# ACAP Incident Response SOP

## Purpose
Define standard incident response actions for security, reliability, and compliance events.

## Severity Levels
- SEV-1: Active breach, sustained outage, or integrity compromise.
- SEV-2: Major feature degradation with business impact.
- SEV-3: Minor degradation or localized non-critical issue.

## Initial Triage (0-15 minutes)
1. Create incident record with timestamp, reporter, impact, and scope.
2. Confirm severity based on user impact and data integrity risk.
3. Assign incident commander and communications owner.
4. Capture first evidence snapshot:
   - `GET /api/v1/logs/system/errors/trace-groups`
   - Relevant Grafana dashboard screenshots
   - Prometheus alert details

## Containment (15-60 minutes)
1. Isolate affected components or tenant paths if needed.
2. Revoke compromised credentials/tokens.
3. Apply temporary mitigations (rate limiting, feature flag disablement, route blocking).
4. Preserve forensic evidence (logs, request IDs, trace IDs, DB audit rows).

## Eradication and Recovery
1. Deploy validated fix through standard release pipeline.
2. Run focused tests for affected controls.
3. Verify service health (`/readyz`, alerts cleared, error rate normalized).
4. Monitor elevated logs and traces for at least one business cycle.

## Communications
- Internal updates every 30 minutes for SEV-1, every 60 minutes for SEV-2.
- Stakeholder summary includes impact, mitigation status, and ETA.

## Post-Incident Review (within 48 hours)
1. Build timeline (detection, triage, containment, recovery).
2. Identify root cause and control gaps.
3. Define corrective/preventive actions with owners and deadlines.
4. Attach evidence pack and final report to governance records.
