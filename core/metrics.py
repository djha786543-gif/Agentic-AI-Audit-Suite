"""
core/metrics.py
Prometheus-compatible metrics registry and helpers.
"""
from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest

REGISTRY = CollectorRegistry()

HTTP_REQUESTS_TOTAL = Counter(
    "acap_http_requests_total",
    "Total HTTP requests handled by ACAP",
    ["method", "path", "status"],
    registry=REGISTRY,
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "acap_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=REGISTRY,
)


def render_metrics() -> bytes:
    return generate_latest(REGISTRY)


def metrics_content_type() -> str:
    return CONTENT_TYPE_LATEST
