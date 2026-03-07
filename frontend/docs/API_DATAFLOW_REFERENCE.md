# API and Dataflow Reference

## Purpose
Provide a practical mapping between portal interactions and backend dataflow patterns.

## API Routing Baseline
Primary router registration is in `api/v1/api_router.py` with modules for:
- auth
- audit/evidence
- engagement/grc/evaluation/engine
- governance/alerts/reports
- findings/uat/system_logs/ai_decisions

## Core Frontend -> API Patterns
### Governance page
- Reads KPI and risk posture APIs.
- Performs policy/framework/risk CRUD operations.
- Includes fallback behavior when endpoints are unavailable.

### Vault page
- Reads evidence vault and run counters.
- Reads intelligence dashboard feed.
- Maintains local encrypted cache fallback flow.

### Reports page
- Reads risk heatmap.
- Calls report export/review-package endpoints.

### UAT page
- Reads report inventory and run status.
- Starts/stops UAT and autopilot lifecycle endpoints.

## Fallback and Continuity Model
- Several pages provide local/demo continuity paths when APIs fail.
- This supports training/demo continuity but should be governed in production.

## Logging and Explainability Dataflow
- System/workflow logs exposed via `/api/v1/logs/*`.
- Explainability decision retrieval via `/api/v1/ai_decisions/{id}`.

## Control Integrity Expectations
- API responses should preserve identifiers and timestamps for audit traceability.
- High-risk exceptions should connect to evidence lineage paths.
- Reporting outputs should reflect latest governance state before publication.

## Validation Checklist
1. Confirm API health and auth before test execution.
2. Verify endpoint responses for all active pages.
3. Validate fallback paths only where intentionally allowed.
4. Confirm logging visibility for key workflow events.
5. Confirm report exports align with current cycle data.
