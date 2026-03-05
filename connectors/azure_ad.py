"""
connectors/azure_ad.py
──────────────────────
Microsoft Azure Active Directory connector.

Pulls user and group data from the Microsoft Graph API to feed the
Logical Access and SOD engines.

Modes
-----
**Mock mode** (default — no Azure credentials required):
    Returns a realistic synthetic dataset so the engine can run immediately
    without any Azure tenant.

**Real mode** (set AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET
in your .env):
    Authenticates via client-credentials OAuth2 flow and calls the real
    Microsoft Graph /users and /groups endpoints.

Environment Variables
---------------------
    AZURE_TENANT_ID     — Azure AD tenant GUID or domain
    AZURE_CLIENT_ID     — App registration client ID
    AZURE_CLIENT_SECRET — App registration client secret
    AZURE_GRAPH_TIMEOUT — HTTP timeout in seconds (default: 10)
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

from connectors.base import BaseConnector, ConnectorResult

logger = logging.getLogger(__name__)

# ── Optional real-mode imports (requests is in requirements.txt) ──────────────
try:
    import requests as _requests

    _REQUESTS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _REQUESTS_AVAILABLE = False


# ── Mock dataset ─────────────────────────────────────────────────────────────

_MOCK_USERS: List[Dict[str, Any]] = [
    {
        "user_id": "U001",
        "username": "alice.chen",
        "display_name": "Alice Chen",
        "department": "Finance",
        "status": "active",
        "roles": ["journal_create", "journal_approve", "account_create"],
        "mfa_enabled": True,
        "last_login_date": "2026-01-15",
        "access_review_date": "2025-10-01",
    },
    {
        "user_id": "U002",
        "username": "bob.jones",
        "display_name": "Bob Jones",
        "department": "IT",
        "status": "active",
        "roles": ["user_create", "role_assign", "code_deploy", "change_approve"],
        "mfa_enabled": False,
        "last_login_date": "2026-02-20",
        "access_review_date": "2026-01-05",
    },
    {
        "user_id": "U003",
        "username": "carol.smith",
        "display_name": "Carol Smith",
        "department": "Accounts Payable",
        "status": "terminated",
        "termination_date": "2026-01-31",
        "roles": ["create_vendor", "pay_vendor", "invoice_entry"],
        "mfa_enabled": True,
        "last_login_date": "2026-02-10",
        "access_review_date": "2025-09-01",
    },
    {
        "user_id": "U004",
        "username": "svc_batch_payments",
        "display_name": "Batch Payments Service",
        "department": "IT Operations",
        "status": "active",
        "roles": ["payment_release", "invoice_create"],
        "mfa_enabled": False,
        "last_login_date": "2026-02-28",
        "access_review_date": None,
    },
    {
        "user_id": "U005",
        "username": "david.wang",
        "display_name": "David Wang",
        "department": "Payroll",
        "status": "active",
        "roles": ["payroll_setup", "payroll_approve", "salary_change", "employee_create"],
        "mfa_enabled": True,
        "last_login_date": "2025-11-01",
        "access_review_date": "2025-08-15",
    },
    {
        "user_id": "U006",
        "username": "emma.wilson",
        "display_name": "Emma Wilson",
        "department": "Finance",
        "status": "active",
        "roles": ["journal_entry", "journal_post", "account_create", "period_close"],
        "mfa_enabled": True,
        "last_login_date": "2026-02-25",
        "access_review_date": "2026-01-10",
    },
]

_MOCK_GROUPS: List[Dict[str, Any]] = [
    {"id": "G001", "display_name": "Finance - AP Team", "member_count": 8},
    {"id": "G002", "display_name": "IT Administrators", "member_count": 3},
    {"id": "G003", "display_name": "Payroll Processing", "member_count": 5},
    {"id": "G004", "display_name": "External Read-Only Auditors", "member_count": 12},
]


# ─────────────────────────────────────────────────────────────────────────────


class AzureADConnector(BaseConnector):
    """
    Microsoft Azure Active Directory connector.

    Implements :class:`connectors.base.BaseConnector`.
    """

    connector_id: str = "azure_ad"
    display_name: str = "Microsoft Azure Active Directory"
    version: str = "1.0.0"

    _GRAPH_BASE = "https://graph.microsoft.com/v1.0"
    _TOKEN_URL_TEMPLATE = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"

    def __init__(self) -> None:
        self._tenant_id: Optional[str] = os.getenv("AZURE_TENANT_ID")
        self._client_id: Optional[str] = os.getenv("AZURE_CLIENT_ID")
        self._client_secret: Optional[str] = os.getenv("AZURE_CLIENT_SECRET")
        self._timeout: int = int(os.getenv("AZURE_GRAPH_TIMEOUT", "10"))
        self._access_token: Optional[str] = None
        self._mock_mode: bool = not all(
            [self._tenant_id, self._client_id, self._client_secret]
        )

        if self._mock_mode:
            logger.info(
                "AzureADConnector: running in MOCK mode "
                "(set AZURE_TENANT_ID / AZURE_CLIENT_ID / AZURE_CLIENT_SECRET for real mode)"
            )

    # ── BaseConnector interface ───────────────────────────────────────────────

    async def authenticate(self) -> None:
        """Obtain a client-credentials bearer token from Azure AD."""
        if self._mock_mode:
            self._access_token = "mock-token"
            return

        if not _REQUESTS_AVAILABLE:
            raise RuntimeError("'requests' package is not installed.")

        url = self._TOKEN_URL_TEMPLATE.format(tenant_id=self._tenant_id)
        payload = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "scope": "https://graph.microsoft.com/.default",
        }
        resp = _requests.post(url, data=payload, timeout=self._timeout)
        resp.raise_for_status()
        self._access_token = resp.json()["access_token"]
        logger.info("AzureADConnector: authenticated successfully")

    async def fetch(
        self,
        org_id: str = "default-org",
        include_groups: bool = True,
        **kwargs: Any,
    ) -> ConnectorResult:
        """
        Fetch users (and optionally groups) from Azure AD.

        Parameters
        ----------
        org_id:
            Tenant identifier attached to every returned record.
        include_groups:
            When True, also fetch group membership data.
        """
        t0 = self._start_timer()
        await self.authenticate()

        errors: List[str] = []

        if self._mock_mode:
            users = [dict(u, org_id=org_id) for u in _MOCK_USERS]
            groups = [dict(g, org_id=org_id) for g in _MOCK_GROUPS] if include_groups else []
        else:
            users, groups = await self._fetch_real(org_id, include_groups, errors)

        records = users + groups
        elapsed = self._elapsed(t0)

        logger.info(
            "AzureADConnector.fetch: org=%s users=%d groups=%d mock=%s elapsed=%.3fs",
            org_id,
            len(users),
            len(groups),
            self._mock_mode,
            elapsed,
        )

        return ConnectorResult(
            connector_id=self.connector_id,
            source_system="Azure Active Directory",
            records=records,
            errors=errors,
            elapsed_seconds=elapsed,
            metadata={
                "mock_mode": self._mock_mode,
                "users_fetched": len(users),
                "groups_fetched": len(groups),
                "org_id": org_id,
            },
        )

    async def health_check(self) -> Dict[str, Any]:
        """Ping the Graph API (or return mock status) and report latency."""
        t0 = time.monotonic()

        if self._mock_mode:
            latency_ms = round((time.monotonic() - t0) * 1000, 1)
            return {
                "connector_id": self.connector_id,
                "display_name": self.display_name,
                "status": "healthy",
                "mode": "mock",
                "latency_ms": latency_ms,
                "message": "Mock mode active — no Azure credentials configured",
            }

        # Real mode: attempt a lightweight Graph call
        if not _REQUESTS_AVAILABLE:
            return {
                "connector_id": self.connector_id,
                "status": "degraded",
                "mode": "real",
                "latency_ms": 0,
                "message": "'requests' package not installed",
            }

        try:
            await self.authenticate()
            url = f"{self._GRAPH_BASE}/organization"
            headers = {"Authorization": f"Bearer {self._access_token}"}
            resp = _requests.get(url, headers=headers, timeout=self._timeout)
            latency_ms = round((time.monotonic() - t0) * 1000, 1)

            if resp.status_code == 200:
                return {
                    "connector_id": self.connector_id,
                    "display_name": self.display_name,
                    "status": "healthy",
                    "mode": "real",
                    "latency_ms": latency_ms,
                    "http_status": resp.status_code,
                }
            return {
                "connector_id": self.connector_id,
                "status": "degraded",
                "mode": "real",
                "latency_ms": latency_ms,
                "http_status": resp.status_code,
                "message": f"Graph API returned {resp.status_code}",
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "connector_id": self.connector_id,
                "status": "unreachable",
                "mode": "real",
                "latency_ms": 0,
                "message": str(exc),
            }

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _fetch_real(
        self,
        org_id: str,
        include_groups: bool,
        errors: List[str],
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Call Microsoft Graph API and return (users, groups)."""
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "ConsistencyLevel": "eventual",
        }

        users_url = (
            f"{self._GRAPH_BASE}/users"
            "?$select=id,userPrincipalName,displayName,department,"
            "accountEnabled,createdDateTime"
            "&$top=999"
        )

        users: List[Dict[str, Any]] = []
        try:
            resp = _requests.get(users_url, headers=headers, timeout=self._timeout)
            resp.raise_for_status()
            for u in resp.json().get("value", []):
                users.append(
                    {
                        "user_id": u.get("id"),
                        "username": u.get("userPrincipalName"),
                        "display_name": u.get("displayName"),
                        "department": u.get("department"),
                        "status": "active" if u.get("accountEnabled") else "inactive",
                        "roles": [],  # Graph requires separate calls per user
                        "mfa_enabled": None,  # Requires /reports/credentialUserRegistrationDetails
                        "org_id": org_id,
                    }
                )
        except Exception as exc:
            errors.append(f"users fetch failed: {exc}")
            logger.error("AzureADConnector: users fetch error: %s", exc)

        groups: List[Dict[str, Any]] = []
        if include_groups:
            groups_url = (
                f"{self._GRAPH_BASE}/groups"
                "?$select=id,displayName,membershipRule"
                "&$top=100"
            )
            try:
                resp = _requests.get(groups_url, headers=headers, timeout=self._timeout)
                resp.raise_for_status()
                for g in resp.json().get("value", []):
                    groups.append(
                        {
                            "id": g.get("id"),
                            "display_name": g.get("displayName"),
                            "org_id": org_id,
                        }
                    )
            except Exception as exc:
                errors.append(f"groups fetch failed: {exc}")
                logger.error("AzureADConnector: groups fetch error: %s", exc)

        return users, groups


# ── Convenience singleton ─────────────────────────────────────────────────────
#: Pre-instantiated connector used by the health endpoint registry.
azure_ad_connector = AzureADConnector()
