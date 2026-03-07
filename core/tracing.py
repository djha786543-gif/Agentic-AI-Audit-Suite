"""
core/tracing.py
Optional OpenTelemetry tracing bootstrap for FastAPI.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI

from core.config import settings

logger = logging.getLogger(__name__)
_TRACING_INITIALIZED = False


def _normalize_otlp_endpoint(endpoint: Optional[str]) -> Optional[str]:
    if not endpoint:
        return None
    cleaned = endpoint.strip().rstrip("/")
    if not cleaned:
        return None
    if cleaned.endswith("/v1/traces"):
        return cleaned
    return f"{cleaned}/v1/traces"


def init_tracing(app: FastAPI) -> None:
    """Initialize OpenTelemetry tracing if enabled by configuration."""
    global _TRACING_INITIALIZED

    if _TRACING_INITIALIZED or not settings.ENABLE_OTEL_TRACING:
        return

    endpoint = _normalize_otlp_endpoint(settings.OTEL_EXPORTER_OTLP_ENDPOINT)
    if not endpoint:
        logger.warning("ENABLE_OTEL_TRACING=true but OTEL_EXPORTER_OTLP_ENDPOINT is not set; tracing disabled")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
    except Exception as exc:
        logger.warning("OpenTelemetry dependencies unavailable; tracing disabled: %s", exc)
        return

    resource = Resource.create(
        {
            "service.name": settings.OTEL_SERVICE_NAME,
            "service.namespace": "acap",
            "deployment.environment": settings.ENVIRONMENT,
        }
    )
    provider = TracerProvider(
        resource=resource,
        sampler=TraceIdRatioBased(rate=settings.OTEL_TRACES_SAMPLER_RATIO),
    )

    exporter = OTLPSpanExporter(
        endpoint=endpoint,
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    request_id_header = settings.REQUEST_ID_HEADER_NAME.lower()

    def server_request_hook(span, scope):
        if span is None or not span.is_recording():
            return

        headers = dict(scope.get("headers") or [])
        req_id = headers.get(request_id_header.encode("utf-8"))
        if req_id:
            span.set_attribute("acap.request_id", req_id.decode("utf-8", errors="ignore"))

    FastAPIInstrumentor.instrument_app(app, server_request_hook=server_request_hook)
    _TRACING_INITIALIZED = True
    logger.info("OpenTelemetry tracing initialized with OTLP endpoint=%s", endpoint)
