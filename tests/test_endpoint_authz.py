from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from api.v1.endpoints import engine, uat
from core.config import settings


app = FastAPI()
app.include_router(engine.router, prefix="/api/v1/engine")
app.include_router(uat.router, prefix="/api/v1/uat")
client = TestClient(app)


def _auth_header(role: str, username: str = "tester") -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": username,
            "role": role,
            "org_id": "default-org",
        },
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def test_engine_sample_requires_auth() -> None:
    response = client.get("/api/v1/engine/sample/users")
    assert response.status_code == 401


def test_uat_status_forbidden_for_internal_auditor() -> None:
    response = client.get(
        "/api/v1/uat/run/status",
        headers=_auth_header("internal_auditor", username="auditor"),
    )
    assert response.status_code == 403


def test_uat_status_allowed_for_system_admin() -> None:
    response = client.get(
        "/api/v1/uat/run/status",
        headers=_auth_header("system_admin", username="admin"),
    )
    assert response.status_code == 200
    payload = response.json()
    assert "running" in payload


def test_engine_controls_forbidden_for_external_auditor() -> None:
    response = client.post(
        "/api/v1/engine/analyze/controls",
        json={"control_id": "CTRL-1", "status": "pass", "description": "ok"},
        headers=_auth_header("external_auditor", username="external"),
    )
    assert response.status_code == 403


def test_engine_controls_allowed_for_connector_service() -> None:
    response = client.post(
        "/api/v1/engine/analyze/controls",
        json={"control_id": "CTRL-2", "status": "fail", "description": "evidence write"},
        headers=_auth_header("connector_service", username="connector"),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("processed") is True
