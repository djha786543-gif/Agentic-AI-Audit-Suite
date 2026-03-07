"""
api/v1/endpoints/auth.py
──────────────────────────
Authentication endpoints.

POST /auth/login
    Returns a JWT bearer token.  The token embeds 'sub' (username), 'role',
    and 'org_id' so every downstream dependency can resolve the full
    AuthContext without a DB round-trip.

Built-in test accounts (development / demo):
    admin / Audit123!         → INTERNAL_AUDITOR  / default-org
    external / External123!   → EXTERNAL_AUDITOR  / default-org
    connector / Service123!   → CONNECTOR_SERVICE / default-org
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from core import security

router = APIRouter()

# ── Development / demo credential table ──────────────────────────────────────
# Maps username → (password, role, org_id)
_DEMO_USERS: dict = {
    "admin": ("Audit123!", "internal_auditor", "default-org"),
    "external": ("External123!", "external_auditor", "default-org"),
    "connector": ("Service123!", "connector_service", "default-org"),
    "processowner": ("Owner123!", "process_owner", "default-org"),
}


@router.post("/login", summary="Obtain a JWT bearer token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Exchange credentials for a short-lived JWT.

    The token carries three custom claims:
    - ``sub``    — username
    - ``role``   — one of internal_auditor | external_auditor | connector_service
    - ``org_id`` — tenant identifier used for Row-Level Security
    """
    user = _DEMO_USERS.get(form_data.username)
    if user is None or form_data.password != user[0]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    _, role, org_id = user
    token = security.create_access_token(
        data={"sub": form_data.username, "role": role, "org_id": org_id}
    )
    return {"access_token": token, "token_type": "bearer", "role": role}


@router.get("/me", summary="Current user identity")
def me(ctx=Depends(security.get_current_user)):
    """Return the authenticated user's username (from JWT sub claim)."""
    return {"username": ctx}
