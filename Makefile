# Makefile — ACAP Phase 1
# ──────────────────────
# make up        — start all services
# make down      — stop all services
# make logs      — tail API + worker logs
# make watcher   — run watcher agent locally (requires API running)
# make test      — run tests
# make shell     — open psql shell in the DB container

.PHONY: up down logs restart watcher worker beat test shell env

# ── Docker Compose ────────────────────────────────────────

up:
	docker compose up --build -d
	@echo ""
	@echo "  ACAP is starting:"
	@echo "    Dashboard:  http://localhost:8000"
	@echo "    API docs:   http://localhost:8000/docs"
	@echo "    Health:     http://localhost:8000/api/v1/health"
	@echo ""
	@echo "  Waiting for services..."
	@sleep 3
	@docker compose ps

down:
	docker compose down

logs:
	docker compose logs -f api worker

restart:
	docker compose restart api worker

# ── Local dev (no Docker) ─────────────────────────────────
# Requires: PostgreSQL on 5432, Redis on 6379, .env file

dev:
	uvicorn main:app --host 0.0.0.0 --port 8000 --reload

worker:
	celery -A core.celery_app.celery_app worker --loglevel=info -Q extraction,evaluation

beat:
	celery -A core.celery_app.celery_app beat --loglevel=info

watcher:
	python watcher_agent.py

# ── Database ──────────────────────────────────────────────

shell:
	docker compose exec db psql -U postgres -d audit_vault

# Quick SQL to inspect vault
inspect:
	docker compose exec db psql -U postgres -d audit_vault \
	  -c "SELECT control_id, source_system, ai_confidence_score, LEFT(content_hash,12) as hash, hash_verified, recorded_at FROM evidence_vault ORDER BY recorded_at DESC LIMIT 10;"

runs:
	docker compose exec db psql -U postgres -d audit_vault \
	  -c "SELECT id, connector_id, status, rows_extracted, started_at FROM extraction_runs ORDER BY started_at DESC LIMIT 10;"

# ── Setup ─────────────────────────────────────────────────

env:
	@if [ ! -f .env ]; then \
	  cp .env.example .env; \
	  echo "  .env created — edit it before running"; \
	else \
	  echo "  .env already exists"; \
	fi

# ── Tests ─────────────────────────────────────────────────

test:
	python -m pytest tests/ -v

install:
	pip install -r requirements.txt
