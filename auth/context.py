"""
auth/context.py
───────────────
AuthContext — a lightweight dataclass that carries the authenticated user's
identity, role, and tenant (org_id) extracted from the JWT claims.

Used as a FastAPI dependency so every protected endpoint receives a typed
context object instead of raw dict claims.

Usage
-----
    from auth.context import AuthContext, get_auth_context

    @router.get("/me")
    async def me(ctx: AuthContext = Depends(get_auth_context)):
        return {"username": ctx.username, "role": ctx.role, "org_id": ctx.org_id}
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from auth.token_validation import validate_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")


@dataclass
class AuthContext:
    """Authenticated user context extracted from a JWT bearer token."""

    username: str
    role: str
    org_id: str

    @property
    def is_internal_auditor(self) -> bool:
        return self.role == "internal_auditor"

    @property
    def is_external_auditor(self) -> bool:
        return self.role == "external_auditor"

    @property
    def is_connector_service(self) -> bool:
        return self.role == "connector_service"


async def get_auth_context(token: str = Depends(oauth2_scheme)) -> AuthContext:
    """
    FastAPI dependency — decode the JWT and return an ``AuthContext``.

    Raises HTTP 401 for missing / invalid / expired tokens.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        claims = validate_access_token(token)
    except JWTError:
        raise credentials_exception

    return AuthContext(
        username=claims.username,
        role=claims.role,
        org_id=claims.org_id,
    )
