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
    POSTGRES_USER=postgres
    POSTGRES_PASSWORD=your_secure_password
    POSTGRES_HOST=localhost
    POSTGRES_PORT=5432
    POSTGRES_DB=audit_vault
    SECRET_KEY=change-me-to-a-long-random-string
    REDIS_URL=redis://localhost:6379/0
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Dict, Optional, List


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

    # ── HTTP security ───────────────────────────────────────
    # Comma-separated origins in .env, e.g.:
    # CORS_ALLOWED_ORIGINS=https://audit.company.com,https://admin.company.com
    CORS_ALLOWED_ORIGINS: List[str] = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = False
    # Comma-separated hostnames, e.g.:
    # TRUSTED_HOSTS=audit.company.com,localhost,127.0.0.1
    TRUSTED_HOSTS: List[str] = ["*"]
    ENABLE_SECURITY_HEADERS: bool = True
    ENABLE_HTTPS_REDIRECT: bool = False

    # CSRF enforcement is optional by default because most existing endpoints
    # currently use bearer auth; enable in prod when browser cookie auth is added.
    ENABLE_CSRF_PROTECTION: bool = False
    CSRF_HEADER_NAME: str = "X-CSRF-Token"

    # Request audit trail middleware toggle.
    ENABLE_SYSTEM_AUDIT_LOG: bool = True
    ENABLE_REQUEST_ID_HEADER: bool = True
    REQUEST_ID_HEADER_NAME: str = "X-Request-ID"
    STRICT_PRODUCTION_GUARDS: bool = True

    # Prometheus-style HTTP metrics.
    ENABLE_PROMETHEUS_METRICS: bool = True
    PROMETHEUS_METRICS_PATH: str = "/metrics"
    METRICS_TRACK_API_ONLY: bool = True

    # OpenTelemetry tracing (OTLP exporter).
    ENABLE_OTEL_TRACING: bool = False
    OTEL_SERVICE_NAME: str = "acap-api"
    OTEL_EXPORTER_OTLP_ENDPOINT: Optional[str] = None
    OTEL_EXPORTER_OTLP_INSECURE: bool = True
    OTEL_TRACES_SAMPLER_RATIO: float = 1.0

    # Startup DB init behavior. Keep destructive reset disabled by default.
    INIT_DB_ON_STARTUP: bool = True
    RESET_DB_ON_STARTUP: bool = False

    # ── Database — built from parts so .env is readable ──────
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "audit_vault"

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def ASYNC_DATABASE_URI(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
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
    # Enable validation of externally-issued JWTs (Azure AD / Okta / other OIDC IdPs).
    ENABLE_EXTERNAL_IDP_TOKENS: bool = False
    IDP_ISSUERS: List[str] = []
    IDP_AUDIENCES: List[str] = []
    IDP_JWKS_URLS: List[str] = []
    IDP_JWKS_CACHE_TTL_SECONDS: int = 300
    # Claim mapping for external IdP tokens.
    IDP_ROLE_CLAIM_KEYS: List[str] = ["role", "roles", "groups"]
    IDP_ORG_CLAIM_KEYS: List[str] = ["org_id", "tenant", "tid"]
    # Comma separated in .env, e.g.:
    # IDP_ROLE_MAPPING=acap-admin:system_admin,acap-audit-manager:audit_manager
    IDP_ROLE_MAPPING: Dict[str, str] = {}
    IDP_DEFAULT_ROLE: str = "internal_auditor"

    # Optional SAML settings placeholders for enterprise rollout.
    ENABLE_SAML: bool = False
    SAML_ENTITY_ID: Optional[str] = None
    SAML_IDP_METADATA_URL: Optional[str] = None
    SAML_IDP_METADATA_FILE: Optional[str] = None

    # ── Vault behaviour ───────────────────────────────────────
    # Alert threshold: evidence with confidence < this triggers the red pulse
    CONFIDENCE_ALERT_THRESHOLD: int = 75

    @field_validator("CORS_ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_cors_allowed_origins(cls, value):
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return ["*"]
            return [item.strip() for item in cleaned.split(",") if item.strip()]
        return value

    @field_validator("TRUSTED_HOSTS", mode="before")
    @classmethod
    def parse_trusted_hosts(cls, value):
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return ["*"]
            return [item.strip() for item in cleaned.split(",") if item.strip()]
        return value

    @field_validator("IDP_ISSUERS", mode="before")
    @classmethod
    def parse_idp_issuers(cls, value):
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return []
            return [item.strip() for item in cleaned.split(",") if item.strip()]
        return value

    @field_validator("IDP_AUDIENCES", mode="before")
    @classmethod
    def parse_idp_audiences(cls, value):
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return []
            return [item.strip() for item in cleaned.split(",") if item.strip()]
        return value

    @field_validator("IDP_JWKS_URLS", mode="before")
    @classmethod
    def parse_idp_jwks_urls(cls, value):
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return []
            return [item.strip() for item in cleaned.split(",") if item.strip()]
        return value

    @field_validator("IDP_ROLE_CLAIM_KEYS", mode="before")
    @classmethod
    def parse_idp_role_claim_keys(cls, value):
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return ["role", "roles", "groups"]
            return [item.strip() for item in cleaned.split(",") if item.strip()]
        return value

    @field_validator("IDP_ORG_CLAIM_KEYS", mode="before")
    @classmethod
    def parse_idp_org_claim_keys(cls, value):
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return ["org_id", "tenant", "tid"]
            return [item.strip() for item in cleaned.split(",") if item.strip()]
        return value

    @field_validator("IDP_ROLE_MAPPING", mode="before")
    @classmethod
    def parse_idp_role_mapping(cls, value):
        if isinstance(value, dict):
            return {str(k).strip().lower(): str(v).strip() for k, v in value.items() if str(k).strip() and str(v).strip()}
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return {}
            mapping: Dict[str, str] = {}
            for pair in cleaned.split(","):
                token = pair.strip()
                if not token or ":" not in token:
                    continue
                key, role = token.split(":", 1)
                key = key.strip().lower()
                role = role.strip()
                if key and role:
                    mapping[key] = role
            return mapping
        return value


settings = Settings()
