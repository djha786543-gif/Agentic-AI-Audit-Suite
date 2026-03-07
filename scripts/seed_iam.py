"""
scripts/seed_iam.py
Seed enterprise roles, permissions, and role-permission mappings.

Usage:
  /workspaces/Agentic-AI-Audit-Suite/.venv/bin/python scripts/seed_iam.py
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select, text

from auth.rbac import Permission, UserRole
from db.async_session import AsyncSessionLocal
from models.iam import PermissionGrant, Role, RolePermission


ROLE_DESCRIPTIONS = {
    UserRole.SYSTEM_ADMIN.value: "Full platform administration",
    UserRole.INTERNAL_AUDITOR.value: "Audit operations and evidence governance",
    UserRole.AUDIT_MANAGER.value: "Approval oversight and audit governance",
    UserRole.RISK_MANAGER.value: "Risk register and risk treatment operations",
    UserRole.COMPLIANCE_OFFICER.value: "Compliance framework and policy governance",
    UserRole.EXECUTIVE_VIEWER.value: "Read-only executive reporting",
    UserRole.EXTERNAL_AUDITOR.value: "Restricted external assurance read access",
    UserRole.CONNECTOR_SERVICE.value: "Machine account for connector operations",
    UserRole.PROCESS_OWNER.value: "Management response and remediation owner",
}

ROLE_PERMISSIONS = {
    UserRole.SYSTEM_ADMIN.value: [p.value for p in Permission],
    UserRole.INTERNAL_AUDITOR.value: [
        Permission.VIEW_DASHBOARD.value,
        Permission.VIEW_REPORTS.value,
        Permission.GENERATE_REPORTS.value,
        Permission.MANAGE_POLICIES.value,
        Permission.MANAGE_FRAMEWORKS.value,
        Permission.MANAGE_RISKS.value,
        Permission.REVIEW_FINDINGS.value,
        Permission.APPROVE_WORKFLOW.value,
        Permission.MANAGE_ENGAGEMENTS.value,
        Permission.RUN_CONNECTORS.value,
        Permission.WRITE_EVIDENCE.value,
        Permission.VIEW_AUDIT_LOGS.value,
    ],
    UserRole.AUDIT_MANAGER.value: [
        Permission.VIEW_DASHBOARD.value,
        Permission.VIEW_REPORTS.value,
        Permission.GENERATE_REPORTS.value,
        Permission.REVIEW_FINDINGS.value,
        Permission.APPROVE_WORKFLOW.value,
        Permission.MANAGE_ENGAGEMENTS.value,
        Permission.VIEW_AUDIT_LOGS.value,
    ],
    UserRole.RISK_MANAGER.value: [
        Permission.VIEW_DASHBOARD.value,
        Permission.VIEW_REPORTS.value,
        Permission.MANAGE_RISKS.value,
        Permission.REVIEW_FINDINGS.value,
    ],
    UserRole.COMPLIANCE_OFFICER.value: [
        Permission.VIEW_DASHBOARD.value,
        Permission.VIEW_REPORTS.value,
        Permission.MANAGE_POLICIES.value,
        Permission.MANAGE_FRAMEWORKS.value,
        Permission.VIEW_AUDIT_LOGS.value,
    ],
    UserRole.EXECUTIVE_VIEWER.value: [
        Permission.VIEW_DASHBOARD.value,
        Permission.VIEW_REPORTS.value,
    ],
    UserRole.EXTERNAL_AUDITOR.value: [
        Permission.VIEW_DASHBOARD.value,
        Permission.VIEW_REPORTS.value,
        Permission.REVIEW_FINDINGS.value,
    ],
    UserRole.CONNECTOR_SERVICE.value: [
        Permission.WRITE_EVIDENCE.value,
        Permission.RUN_CONNECTORS.value,
    ],
    UserRole.PROCESS_OWNER.value: [
        Permission.REVIEW_FINDINGS.value,
    ],
}


async def seed_iam(org_id: str = "default-org") -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("SELECT set_config('app.current_tenant', :tenant, true)"),
            {"tenant": org_id},
        )

        permission_ids = {}
        for permission in Permission:
            existing = await db.execute(
                select(PermissionGrant).filter(
                    PermissionGrant.org_id == org_id,
                    PermissionGrant.permission_key == permission.value,
                )
            )
            permission_row = existing.scalars().first()
            if not permission_row:
                permission_row = PermissionGrant(
                    org_id=org_id,
                    permission_key=permission.value,
                    description=permission.value.replace("_", " ").title(),
                )
                db.add(permission_row)
                await db.flush()
            permission_ids[permission.value] = permission_row.id

        role_ids = {}
        for role in UserRole:
            existing = await db.execute(
                select(Role).filter(
                    Role.org_id == org_id,
                    Role.role_key == role.value,
                )
            )
            role_row = existing.scalars().first()
            if not role_row:
                role_row = Role(
                    org_id=org_id,
                    role_key=role.value,
                    name=role.value.replace("_", " ").title(),
                    description=ROLE_DESCRIPTIONS.get(role.value),
                    is_system=True,
                )
                db.add(role_row)
                await db.flush()
            role_ids[role.value] = role_row.id

        for role_key, perms in ROLE_PERMISSIONS.items():
            role_id = role_ids[role_key]
            for permission_key in perms:
                permission_id = permission_ids[permission_key]
                existing = await db.execute(
                    select(RolePermission).filter(
                        RolePermission.org_id == org_id,
                        RolePermission.role_id == role_id,
                        RolePermission.permission_id == permission_id,
                    )
                )
                if existing.scalars().first() is None:
                    db.add(
                        RolePermission(
                            org_id=org_id,
                            role_id=role_id,
                            permission_id=permission_id,
                        )
                    )

        await db.commit()
        print("IAM seed complete for org:", org_id)


if __name__ == "__main__":
    asyncio.run(seed_iam())
