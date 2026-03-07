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
SYSTEM_ADMIN        Full platform administration.
INTERNAL_AUDITOR    Full audit operations access.
AUDIT_MANAGER       Audit workflow approvals + oversight.
RISK_MANAGER        Risk register + governance operations.
COMPLIANCE_OFFICER  Compliance framework and mapping operations.
EXECUTIVE_VIEWER    Read-only executive and reporting access.
EXTERNAL_AUDITOR    Restricted read access.
CONNECTOR_SERVICE   Machine-to-machine evidence and controls writes.
PROCESS_OWNER       Management response and remediation owner operations.
"""
from __future__ import annotations

import enum
from typing import Callable

from fastapi import Depends, HTTPException, status

from auth.context import AuthContext, get_auth_context


class UserRole(str, enum.Enum):
    SYSTEM_ADMIN = "system_admin"
    INTERNAL_AUDITOR = "internal_auditor"
    AUDIT_MANAGER = "audit_manager"
    RISK_MANAGER = "risk_manager"
    COMPLIANCE_OFFICER = "compliance_officer"
    EXECUTIVE_VIEWER = "executive_viewer"
    EXTERNAL_AUDITOR = "external_auditor"
    CONNECTOR_SERVICE = "connector_service"
    PROCESS_OWNER = "process_owner"


# ── Permission hierarchy ─────────────────────────────────────────────────────
# Maps each role to the set of roles it is allowed to impersonate/act as.
# A role is always in its own set (self-permission).
_ROLE_GRANTS: dict[UserRole, set[UserRole]] = {
    UserRole.SYSTEM_ADMIN: {
        UserRole.SYSTEM_ADMIN,
        UserRole.INTERNAL_AUDITOR,
        UserRole.AUDIT_MANAGER,
        UserRole.RISK_MANAGER,
        UserRole.COMPLIANCE_OFFICER,
        UserRole.EXECUTIVE_VIEWER,
        UserRole.EXTERNAL_AUDITOR,
        UserRole.CONNECTOR_SERVICE,
        UserRole.PROCESS_OWNER,
    },
    UserRole.INTERNAL_AUDITOR: {
        UserRole.INTERNAL_AUDITOR,
        UserRole.AUDIT_MANAGER,
        UserRole.RISK_MANAGER,
        UserRole.COMPLIANCE_OFFICER,
        UserRole.EXECUTIVE_VIEWER,
        UserRole.EXTERNAL_AUDITOR,
        UserRole.CONNECTOR_SERVICE,
        UserRole.PROCESS_OWNER,
    },
    UserRole.AUDIT_MANAGER: {
        UserRole.AUDIT_MANAGER,
        UserRole.EXECUTIVE_VIEWER,
        UserRole.EXTERNAL_AUDITOR,
    },
    UserRole.RISK_MANAGER: {
        UserRole.RISK_MANAGER,
        UserRole.EXECUTIVE_VIEWER,
    },
    UserRole.COMPLIANCE_OFFICER: {
        UserRole.COMPLIANCE_OFFICER,
        UserRole.EXECUTIVE_VIEWER,
    },
    UserRole.EXECUTIVE_VIEWER: {
        UserRole.EXECUTIVE_VIEWER,
    },
    UserRole.EXTERNAL_AUDITOR: {
        UserRole.EXTERNAL_AUDITOR,
    },
    UserRole.CONNECTOR_SERVICE: {
        UserRole.CONNECTOR_SERVICE,
    },
    UserRole.PROCESS_OWNER: {
        UserRole.PROCESS_OWNER,
    },
}


class Permission(str, enum.Enum):
    VIEW_DASHBOARD = "view_dashboard"
    VIEW_REPORTS = "view_reports"
    GENERATE_REPORTS = "generate_reports"
    MANAGE_POLICIES = "manage_policies"
    MANAGE_FRAMEWORKS = "manage_frameworks"
    MANAGE_RISKS = "manage_risks"
    REVIEW_FINDINGS = "review_findings"
    APPROVE_WORKFLOW = "approve_workflow"
    MANAGE_USERS = "manage_users"
    MANAGE_ENGAGEMENTS = "manage_engagements"
    RUN_CONNECTORS = "run_connectors"
    WRITE_EVIDENCE = "write_evidence"
    VIEW_AUDIT_LOGS = "view_audit_logs"


_ROLE_PERMISSIONS: dict[UserRole, set[Permission]] = {
    UserRole.SYSTEM_ADMIN: set(Permission),
    UserRole.INTERNAL_AUDITOR: {
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_REPORTS,
        Permission.GENERATE_REPORTS,
        Permission.MANAGE_POLICIES,
        Permission.MANAGE_FRAMEWORKS,
        Permission.MANAGE_RISKS,
        Permission.REVIEW_FINDINGS,
        Permission.APPROVE_WORKFLOW,
        Permission.MANAGE_ENGAGEMENTS,
        Permission.RUN_CONNECTORS,
        Permission.WRITE_EVIDENCE,
        Permission.VIEW_AUDIT_LOGS,
    },
    UserRole.AUDIT_MANAGER: {
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_REPORTS,
        Permission.GENERATE_REPORTS,
        Permission.REVIEW_FINDINGS,
        Permission.APPROVE_WORKFLOW,
        Permission.MANAGE_ENGAGEMENTS,
        Permission.VIEW_AUDIT_LOGS,
    },
    UserRole.RISK_MANAGER: {
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_REPORTS,
        Permission.MANAGE_RISKS,
        Permission.REVIEW_FINDINGS,
    },
    UserRole.COMPLIANCE_OFFICER: {
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_REPORTS,
        Permission.MANAGE_POLICIES,
        Permission.MANAGE_FRAMEWORKS,
        Permission.VIEW_AUDIT_LOGS,
    },
    UserRole.EXECUTIVE_VIEWER: {
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_REPORTS,
    },
    UserRole.EXTERNAL_AUDITOR: {
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_REPORTS,
        Permission.REVIEW_FINDINGS,
    },
    UserRole.CONNECTOR_SERVICE: {
        Permission.WRITE_EVIDENCE,
        Permission.RUN_CONNECTORS,
    },
    UserRole.PROCESS_OWNER: {
        Permission.REVIEW_FINDINGS,
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


def require_permission(*required_permissions: Permission) -> Callable:
    """
    FastAPI dependency factory for permission-based endpoint authorization.
    """

    async def dependency(ctx: AuthContext = Depends(get_auth_context)) -> AuthContext:
        user_role = UserRole(ctx.role) if ctx.role in UserRole._value2member_map_ else None
        if user_role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Unrecognised role '{ctx.role}' — access denied.",
            )

        granted = _ROLE_PERMISSIONS.get(user_role, set())
        if not all(permission in granted for permission in required_permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Role '{user_role.value}' does not have required permissions. "
                    f"Required: {[p.value for p in required_permissions]}"
                ),
            )
        return ctx

    return dependency
