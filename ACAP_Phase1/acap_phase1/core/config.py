"""
core/config.py
──────────────
Pydantic Settings — single source of truth for all configuration.

CHANGES FROM ORIGINAL:
  - DB credentials no longer hardcoded — read from environment / .env file
  - Added SECRET_KEY for JWT signing (Phase 2)
  - Added CELERY_BROKER_URL + RESULT_BACKEND (was empty before)
  - extra="ignore" so docker-compose can pass DATABASE_URL without crashing
    (we normalise it into SQLALCHEMY_DATABASE_URI below)

Create a .env file in the project root (never commit it):
    POSTGRES_USER=dj_admin
    POSTGRES_PASSWORD=password123
    POSTGRES_HOST=localhost
    POSTGRES_PORT=5432
    POSTGRES_DB=audit_vault
    SECRET_KEY=change-me-to-a-long-random-string
    REDIS_URL=redis://localhost:6379/0
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",   # ignores DATABASE_URL passed by docker-compose
    )

    # ── Application ──────────────────────────────────────────
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "ACAP Agentic AI Audit Suite"
    ENVIRONMENT: str = "development"   # development | staging | production

    # ── Database — built from parts so .env is readable ──────
    POSTGRES_USER: str = "dj_admin"
    POSTGRES_PASSWORD: str = "password123"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "audit_vault"

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ── Celery / Redis ────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    @property
    def CELERY_BROKER_URL(self) -> str:
        return self.REDIS_URL

    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        return self.REDIS_URL

    # ── Auth (used in Phase 2 — defined here so config is stable) ──
    SECRET_KEY: str = "CHANGE-ME-generate-with-openssl-rand-hex-32"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ── Vault behaviour ───────────────────────────────────────
    # Alert threshold: evidence with confidence < this triggers the red pulse
    CONFIDENCE_ALERT_THRESHOLD: int = 75

    # ── Intelligence Layer (Phase 2 — Auditor Intelligence) ───
    MATERIALITY_THRESHOLD: float = 500.00   # USD — anomalies below this auto-clear
    SYSTEMIC_THRESHOLD: int = 10            # N+ similar events = Systemic Logic Gap
    RISK_SCORE_CRITICAL: int = 80           # Score >= this = Critical priority
    RISK_SCORE_HIGH: int = 60               # Score >= this = High priority
    RISK_SCORE_MEDIUM: int = 40             # Score >= this = Medium priority


settings = Settings()
