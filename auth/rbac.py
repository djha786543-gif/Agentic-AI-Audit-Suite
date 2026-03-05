"""
auth/rbac.py
────────────
Role-Based Access Control for the ACAP API.

Defines the canonical ``UserRole`` enum and the ``require_role()`` FastAPI
dependency factory.

Usage
-----
    from auth.rbac import UserRole, require_role

    @router.post("/evidence")
    async def submit_evidence(
        _: AuthContext = Depends(require_role(UserRole.INTERNAL_AUDITOR)),
    ):
        ...

Roles
-----
INTERNAL_AUDITOR    Full read + write access.
EXTERNAL_AUDITOR    Read-only access to vault + evaluation results.
CONNECTOR_SERVICE   Machine-to-machine: write evidence + read own runs.
"""
from __future__ import annotations

import enum
from typing import Callable

from fastapi import Depends, HTTPException, status

from auth.context import AuthContext, get_auth_context


class UserRole(str, enum.Enum):
    INTERNAL_AUDITOR = "internal_auditor"
    EXTERNAL_AUDITOR = "external_auditor"
    CONNECTOR_SERVICE = "connector_service"


# ── Permission hierarchy ─────────────────────────────────────────────────────
# Maps each role to the set of roles it is allowed to impersonate/act as.
# A role is always in its own set (self-permission).
_ROLE_GRANTS: dict[UserRole, set[UserRole]] = {
    UserRole.INTERNAL_AUDITOR: {
        UserRole.INTERNAL_AUDITOR,
        UserRole.EXTERNAL_AUDITOR,
        UserRole.CONNECTOR_SERVICE,
    },
    UserRole.EXTERNAL_AUDITOR: {
        UserRole.EXTERNAL_AUDITOR,
    },
    UserRole.CONNECTOR_SERVICE: {
        UserRole.CONNECTOR_SERVICE,
    },
}


def require_role(*required_roles: UserRole) -> Callable:
    """
    FastAPI dependency factory.

    Returns a dependency that resolves the current ``AuthContext`` and raises
    HTTP 403 if the authenticated user does not hold at least one of the
    ``required_roles``.

    Example
    -------
        @router.get("/sensitive")
        async def sensitive_endpoint(
            ctx: AuthContext = Depends(require_role(UserRole.INTERNAL_AUDITOR)),
        ):
            return {"user": ctx.username}
    """

    async def dependency(ctx: AuthContext = Depends(get_auth_context)) -> AuthContext:
        user_role = UserRole(ctx.role) if ctx.role in UserRole._value2member_map_ else None
        if user_role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Unrecognised role '{ctx.role}' — access denied.",
            )
        granted = _ROLE_GRANTS.get(user_role, set())
        if not any(r in granted for r in required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Role '{user_role.value}' does not have permission for this endpoint. "
                    f"Required: {[r.value for r in required_roles]}"
                ),
            )
        return ctx

    return dependency
