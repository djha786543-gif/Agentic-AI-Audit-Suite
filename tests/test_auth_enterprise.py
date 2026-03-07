import unittest

from fastapi import HTTPException
from jose import jwt

from auth.context import AuthContext
from auth.rbac import Permission, require_permission
from auth.token_validation import validate_access_token
from core.config import settings


class TestEnterpriseAuthHardening(unittest.IsolatedAsyncioTestCase):
    def test_validate_access_token_local_jwt(self):
        token = jwt.encode(
            {
                "sub": "alice@example.com",
                "role": "audit_manager",
                "org_id": "org-enterprise",
            },
            settings.SECRET_KEY,
            algorithm="HS256",
        )

        claims = validate_access_token(token)

        self.assertEqual(claims.username, "alice@example.com")
        self.assertEqual(claims.role, "audit_manager")
        self.assertEqual(claims.org_id, "org-enterprise")

    async def test_require_permission_blocks_and_allows_by_role(self):
        dependency = require_permission(Permission.MANAGE_USERS)

        with self.assertRaises(HTTPException) as denied:
            await dependency(
                AuthContext(
                    username="auditor",
                    role="internal_auditor",
                    org_id="org-1",
                )
            )
        self.assertEqual(denied.exception.status_code, 403)

        allowed = await dependency(
            AuthContext(
                username="admin",
                role="system_admin",
                org_id="org-1",
            )
        )
        self.assertEqual(allowed.role, "system_admin")

    async def test_manage_engagements_allowed_for_audit_manager(self):
        dependency = require_permission(Permission.MANAGE_ENGAGEMENTS)
        allowed = await dependency(
            AuthContext(
                username="manager",
                role="audit_manager",
                org_id="org-1",
            )
        )
        self.assertEqual(allowed.role, "audit_manager")


if __name__ == "__main__":
    unittest.main()
