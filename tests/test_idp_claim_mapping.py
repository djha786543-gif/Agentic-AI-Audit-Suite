import unittest

from jose import jwt

from auth.token_validation import validate_access_token
from core.config import settings


class TestIdpClaimMapping(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_role_claim_keys = list(settings.IDP_ROLE_CLAIM_KEYS)
        self._orig_org_claim_keys = list(settings.IDP_ORG_CLAIM_KEYS)
        self._orig_role_mapping = dict(settings.IDP_ROLE_MAPPING)
        self._orig_default_role = settings.IDP_DEFAULT_ROLE

    def tearDown(self) -> None:
        settings.IDP_ROLE_CLAIM_KEYS = self._orig_role_claim_keys
        settings.IDP_ORG_CLAIM_KEYS = self._orig_org_claim_keys
        settings.IDP_ROLE_MAPPING = self._orig_role_mapping
        settings.IDP_DEFAULT_ROLE = self._orig_default_role

    def test_role_mapping_applied_from_groups(self):
        settings.IDP_ROLE_CLAIM_KEYS = ["groups"]
        settings.IDP_ROLE_MAPPING = {"acap-audit-manager": "audit_manager"}
        settings.IDP_DEFAULT_ROLE = "internal_auditor"

        token = jwt.encode(
            {
                "sub": "idp-user",
                "groups": ["acap-audit-manager"],
                "tid": "tenant-1",
            },
            settings.SECRET_KEY,
            algorithm="HS256",
        )
        claims = validate_access_token(token)

        self.assertEqual(claims.role, "audit_manager")
        self.assertEqual(claims.org_id, "tenant-1")

    def test_default_role_when_unmapped(self):
        settings.IDP_ROLE_CLAIM_KEYS = ["groups"]
        settings.IDP_ROLE_MAPPING = {}
        settings.IDP_DEFAULT_ROLE = "executive_viewer"

        token = jwt.encode(
            {
                "sub": "idp-user",
                "groups": ["unknown-group"],
                "org_id": "org-xyz",
            },
            settings.SECRET_KEY,
            algorithm="HS256",
        )
        claims = validate_access_token(token)

        self.assertEqual(claims.role, "executive_viewer")
        self.assertEqual(claims.org_id, "org-xyz")


if __name__ == "__main__":
    unittest.main()
