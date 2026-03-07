"""
main.py — ACAP FastAPI application
Serves the API + your custom index.html dashboard on /
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi import Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
import os
import logging

from api.v1.api_router import api_router
from core.config import settings
from core.tracing import init_tracing
from core.http_middleware import (
    CSRFMiddleware,
    MetricsMiddleware,
    RequestAuditLogMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from core.metrics import metrics_content_type, render_metrics

logger = logging.getLogger(__name__)


def _enforce_production_guardrails() -> None:
    if settings.ENVIRONMENT.lower() != "production":
        return

    if not settings.STRICT_PRODUCTION_GUARDS:
        logger.warning("STRICT_PRODUCTION_GUARDS disabled in production")
        return

    failures: list[str] = []
    if settings.RESET_DB_ON_STARTUP:
        failures.append("RESET_DB_ON_STARTUP must be false")
    if "*" in settings.CORS_ALLOWED_ORIGINS:
        failures.append("CORS_ALLOWED_ORIGINS cannot include '*'")
    if "*" in settings.TRUSTED_HOSTS:
        failures.append("TRUSTED_HOSTS cannot include '*'")
    if not settings.ENABLE_HTTPS_REDIRECT:
        failures.append("ENABLE_HTTPS_REDIRECT must be true")
    if settings.SECRET_KEY.startswith("CHANGE-ME"):
        failures.append("SECRET_KEY must be explicitly set")

    if failures:
        raise RuntimeError("Production guardrails failed: " + "; ".join(failures))


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ACAP starting — env=%s", settings.ENVIRONMENT)
    _enforce_production_guardrails()
    if settings.INIT_DB_ON_STARTUP:
        from init_db import init_db

        init_db(reset_schema=settings.RESET_DB_ON_STARTUP)
        logger.info(
            "DB init complete with RLS (reset=%s)",
            settings.RESET_DB_ON_STARTUP,
        )
    else:
        logger.info("INIT_DB_ON_STARTUP disabled; skipping startup schema initialization")
    yield
    logger.info("ACAP shutdown")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.1.0",
    docs_url="/docs",
    lifespan=lifespan,
)

if settings.ENABLE_OTEL_TRACING:
    init_tracing(app)

if settings.ENABLE_HTTPS_REDIRECT:
    app.add_middleware(HTTPSRedirectMiddleware)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.TRUSTED_HOSTS,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
)

if settings.ENABLE_SECURITY_HEADERS:
    app.add_middleware(SecurityHeadersMiddleware)

if settings.ENABLE_REQUEST_ID_HEADER:
    app.add_middleware(RequestContextMiddleware)

if settings.ENABLE_CSRF_PROTECTION:
    app.add_middleware(CSRFMiddleware)

if settings.ENABLE_SYSTEM_AUDIT_LOG:
    app.add_middleware(RequestAuditLogMiddleware)

if settings.ENABLE_PROMETHEUS_METRICS:
    app.add_middleware(MetricsMiddleware)

app.include_router(api_router, prefix=settings.API_V1_STR)


if settings.ENABLE_PROMETHEUS_METRICS:
    @app.get(settings.PROMETHEUS_METRICS_PATH, include_in_schema=False)
    async def prometheus_metrics():
        return Response(content=render_metrics(), media_type=metrics_content_type())


from fastapi.staticfiles import StaticFiles
frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
else:
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def dashboard():
        return HTMLResponse(content="<h1>ACAP API running — <a href='/docs'>Open Docs</a></h1>")
