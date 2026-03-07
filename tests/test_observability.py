from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.http_middleware import RequestContextMiddleware


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/ping")
    async def ping():
        return {"status": "ok"}

    return app


def test_request_id_generated_when_missing() -> None:
    client = TestClient(_build_app())
    response = client.get("/ping")
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")


def test_request_id_echoed_when_provided() -> None:
    client = TestClient(_build_app())
    request_id = "req-12345"
    response = client.get("/ping", headers={"X-Request-ID": request_id})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == request_id
