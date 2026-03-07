from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.testclient import TestClient

from core.http_middleware import MetricsMiddleware
from core.metrics import metrics_content_type, render_metrics


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(MetricsMiddleware)

    @app.get("/api/v1/ping")
    async def ping():
        return {"status": "ok"}

    @app.get("/metrics")
    async def metrics():
        return Response(content=render_metrics(), media_type=metrics_content_type())

    return app


def test_metrics_endpoint_exposes_prometheus_format() -> None:
    client = TestClient(_build_app())
    _ = client.get("/api/v1/ping")
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers.get("content-type", "")
    body = response.text
    assert "acap_http_requests_total" in body
    assert "acap_http_request_duration_seconds" in body
    assert 'path="/api/v1/ping"' in body
