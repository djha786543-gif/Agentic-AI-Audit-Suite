# Backend Service Layer

This additive backend package introduces an enterprise service layer under `/backend`
without changing existing UI structure or route semantics.

## Structure
- `backend/api` - API router and compatibility mount
- `backend/auth` - auth adapters and service hooks
- `backend/agents` - agent orchestration modules
- `backend/audit_engine` - audit engine service adapters
- `backend/evidence` - evidence service adapters
- `backend/workflows` - workflow lifecycle services
- `backend/integrations` - optional enterprise connectors

## Run
```bash
uvicorn backend.main:app --reload --port 8010
```

## Backward Compatibility
The backend router mounts the existing `/api/v1` API router so current UI calls continue
working without UI redesign or navigation changes.
