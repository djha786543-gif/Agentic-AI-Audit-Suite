"""
core/http_middleware.py
HTTP security, CSRF checks, and request audit logging middleware.
"""
from __future__ import annotations

import time
import uuid
from typing import Optional

from fastapi import Request
from opentelemetry import trace
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from auth.token_validation import validate_access_token
from core.config import settings
from core.metrics import HTTP_REQUEST_DURATION_SECONDS, HTTP_REQUESTS_TOTAL
from db.async_session import AsyncSessionLocal
from models.system_logs import SystemLog


def _current_trace_context() -> tuple[Optional[str], Optional[str]]:
    span = trace.get_current_span()
    if span is None:
        return None, None

    ctx = span.get_span_context()
    if ctx is None or not getattr(ctx, "is_valid", False):
        return None, None

    trace_id = f"{ctx.trace_id:032x}"
    span_id = f"{ctx.span_id:016x}"
    return trace_id, span_id


def _extract_client_ip(request: Request) -> Optional[str]:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _extract_session_id(request: Request) -> Optional[str]:
    return (
        request.headers.get("x-session-id")
        or request.cookies.get("session_id")
        or request.cookies.get("acap_session")
    )


def _extract_auth_claims(request: Request) -> tuple[Optional[str], Optional[str], str]:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None, None, "default-org"

    token = auth.split(" ", 1)[1].strip()
    try:
        claims = validate_access_token(token)
        return claims.username, claims.role, claims.org_id
    except Exception:
        return None, None, "default-org"


def _infer_action(method: str, path: str, status_code: int) -> str:
    base = {
        "GET": "data_access",
        "POST": "create",
        "PUT": "update",
        "PATCH": "update",
        "DELETE": "delete",
    }.get(method.upper(), "request")

    lowered = path.lower()
    if "/auth/login" in lowered:
        return "user_login" if status_code < 400 else "user_login_failed"
    if "/engine/analyze" in lowered:
        return "ai_decision"
    if "/reports" in lowered and method.upper() in {"POST", "PATCH"}:
        return "report_generation"
    if "/findings/" in lowered and "management-response" in lowered:
        return "workflow_approval"
    if "/evaluation/controls" in lowered:
        return "control_testing"
    return base


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add baseline security headers to all HTTP responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Keep policy conservative to avoid breaking current static frontend.
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self' 'unsafe-inline' 'unsafe-eval' https: data:; frame-ancestors 'none';",
        )
        return response


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request correlation ID for end-to-end tracing."""

    async def dispatch(self, request: Request, call_next):
        header_name = settings.REQUEST_ID_HEADER_NAME
        request_id = request.headers.get(header_name) or str(uuid.uuid4())
        request.state.request_id = request_id

        span = trace.get_current_span()
        if span is not None and span.is_recording():
            span.set_attribute("acap.request_id", request_id)

        response = await call_next(request)
        response.headers.setdefault(header_name, request_id)
        return response


def _resolved_path(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str) and path:
        return path
    return request.url.path


class MetricsMiddleware(BaseHTTPMiddleware):
    """Capture HTTP request metrics for Prometheus scraping."""

    async def dispatch(self, request: Request, call_next):
        track_api_only = settings.METRICS_TRACK_API_ONLY
        if track_api_only and not request.url.path.startswith(settings.API_V1_STR):
            return await call_next(request)

        if request.url.path == settings.PROMETHEUS_METRICS_PATH:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration_seconds = max(time.perf_counter() - start, 0.0)

        method = request.method.upper()
        path = _resolved_path(request)
        status_code = str(response.status_code)

        HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=status_code).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(duration_seconds)
        return response


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    Double-submit CSRF check.

    Enforcement behavior:
    - Only active for mutating methods.
    - Requires a cookie named ``acap_csrf_token``.
    - Requires matching header configured by ``settings.CSRF_HEADER_NAME``.

    If the CSRF cookie is absent, request is allowed (backward-compatible mode).
    """

    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

    async def dispatch(self, request: Request, call_next):
        if request.method.upper() in self.SAFE_METHODS:
            return await call_next(request)

        csrf_cookie = request.cookies.get("acap_csrf_token")
        if not csrf_cookie:
            return await call_next(request)

        csrf_header = request.headers.get(settings.CSRF_HEADER_NAME)
        if not csrf_header or csrf_header != csrf_cookie:
            from starlette.responses import JSONResponse

            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF validation failed"},
            )

        return await call_next(request)


class RequestAuditLogMiddleware(BaseHTTPMiddleware):
    """Persist a system log record for every API request."""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000.0, 2)

        username, role, org_id = _extract_auth_claims(request)
        path = request.url.path

        span = trace.get_current_span()
        if span is not None and span.is_recording():
            if username:
                span.set_attribute("enduser.id", username)
            if role:
                span.set_attribute("acap.user_role", role)
            span.set_attribute("acap.org_id", org_id)
            span.set_attribute("acap.http.duration_ms", duration_ms)

        trace_id, span_id = _current_trace_context()

        # Skip static assets and docs to avoid noisy logs.
        if path.startswith("/api"):
            log_record = SystemLog(
                org_id=org_id,
                user=username,
                role=role,
                action=_infer_action(request.method, path, response.status_code),
                resource=path,
                method=request.method.upper(),
                status_code=response.status_code,
                ip_address=_extract_client_ip(request),
                session_id=_extract_session_id(request),
                user_agent=request.headers.get("user-agent"),
                metadata_json={
                    "query": str(request.url.query or ""),
                    "duration_ms": duration_ms,
                    "request_id": getattr(request.state, "request_id", None),
                    "trace_id": trace_id,
                    "span_id": span_id,
                },
                immutable=True,
            )

            try:
                async with AsyncSessionLocal() as db:
                    await db.execute(
                        text("SELECT set_config('app.current_tenant', :tenant, true)"),
                        {"tenant": org_id or "default-org"},
                    )
                    db.add(log_record)
                    await db.commit()
            except Exception:
                # Never block user requests because audit log write failed.
                pass

        return response
