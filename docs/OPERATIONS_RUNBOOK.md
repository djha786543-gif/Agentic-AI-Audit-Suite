# ACAP Operations Runbook

## Scope
Operational procedures for running ACAP API, workers, monitoring stack, and standard maintenance tasks.

## Core Services
- API: FastAPI (`main.py`)
- Worker: Celery (`worker` service)
- Scheduler: Celery beat (`beat` service)
- Data: PostgreSQL and Redis
- Monitoring: Prometheus, Alertmanager, Grafana, OTEL collector

## Startup Procedure
1. Verify environment variables in `.env` (especially `ENVIRONMENT`, DB, JWT, and observability settings).
2. Start infrastructure:
   - `docker compose up -d`
3. Run migrations:
   - `alembic upgrade head`
4. Seed IAM permissions (first deploy and after role model changes):
   - `python scripts/seed_iam.py`
5. Start API:
   - `uvicorn main:app --host 0.0.0.0 --port 8000`
6. Start workers if not using compose services:
   - `celery -A core.celery_app.celery worker --loglevel=INFO`
   - `celery -A core.celery_app.celery beat --loglevel=INFO`

## Health Checks
- API liveness: `GET /healthz`
- API readiness: `GET /readyz`
- Metrics: `GET /metrics` (if enabled)
- Prometheus UI: `http://localhost:9090`
- Alertmanager: `http://localhost:9093`
- Grafana: `http://localhost:3000`

## Deploy Validation
1. Confirm migrations are at head.
2. Execute quality gates:
   - `pytest -q tests/test_startup_guardrails.py tests/test_endpoint_authz.py tests/test_metrics.py`
3. Validate enterprise auth:
   - `pytest -q tests/test_auth_enterprise.py tests/test_idp_claim_mapping.py`
4. Validate observability:
   - `pytest -q tests/test_observability.py tests/test_tracing.py tests/test_alert_rules_pack.py`

## Evidence Pack Generation
Generate a compliance evidence bundle:
- `make compliance-pack`

Output artifacts:
- `artifacts/compliance-pack-<timestamp>/manifest.json`
- `artifacts/compliance-pack-<timestamp>/checksums.sha256`
- `artifacts/compliance-pack-<timestamp>.zip`

## Routine Maintenance
- Rotate secrets and API keys on schedule.
- Review Alertmanager routes and receivers quarterly.
- Patch base images and Python packages monthly or on critical CVE release.
- Re-run smoke/quality pipelines after all infrastructure or dependency changes.
