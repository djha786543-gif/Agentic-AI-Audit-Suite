"""
auth/token_validation.py
Central token validation for local JWT and external OIDC providers.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests
from jose import JWTError, jwt

from core.config import settings


@dataclass
class TokenClaims:
    username: str
    role: str
    org_id: str
    raw: Dict[str, Any]


_JWKS_CACHE: dict[str, tuple[float, Dict[str, Any]]] = {}


def _get_cached_jwks(url: str) -> Dict[str, Any]:
    now = time.time()
    cached = _JWKS_CACHE.get(url)
    if cached and (now - cached[0]) < settings.IDP_JWKS_CACHE_TTL_SECONDS:
        return cached[1]

    resp = requests.get(url, timeout=5)
    resp.raise_for_status()
    payload = resp.json()
    _JWKS_CACHE[url] = (now, payload)
    return payload


def _decode_local_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        return None


def _decode_external_token(token: str) -> Optional[Dict[str, Any]]:
    if not settings.ENABLE_EXTERNAL_IDP_TOKENS:
        return None
    if not settings.IDP_JWKS_URLS:
        return None

    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    alg = header.get("alg", "RS256")
    if not kid:
        return None

    issuers = settings.IDP_ISSUERS or [None]
    audiences = settings.IDP_AUDIENCES or [None]

    for jwks_url in settings.IDP_JWKS_URLS:
        try:
            jwks = _get_cached_jwks(jwks_url)
            key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
            if not key:
                continue

            for issuer in issuers:
                for audience in audiences:
                    decode_kwargs: Dict[str, Any] = {
                        "algorithms": [alg],
                        "options": {"verify_aud": bool(audience)},
                    }
                    if audience:
                        decode_kwargs["audience"] = audience
                    if issuer:
                        decode_kwargs["issuer"] = issuer

                    try:
                        payload = jwt.decode(token, key, **decode_kwargs)
                        return payload
                    except Exception:
                        continue
        except Exception:
            continue
    return None


def _derive_username(payload: Dict[str, Any]) -> str:
    return (
        str(payload.get("sub") or "").strip()
        or str(payload.get("preferred_username") or "").strip()
        or str(payload.get("upn") or "").strip()
        or str(payload.get("email") or "").strip()
    )


def _derive_role(payload: Dict[str, Any]) -> str:
    role_mapping = {k.lower(): v for k, v in (settings.IDP_ROLE_MAPPING or {}).items()}

    for key in settings.IDP_ROLE_CLAIM_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            candidate = value.strip()
            mapped = role_mapping.get(candidate.lower())
            if mapped:
                return mapped
            if candidate in {
                "system_admin",
                "internal_auditor",
                "audit_manager",
                "risk_manager",
                "compliance_officer",
                "executive_viewer",
                "external_auditor",
                "connector_service",
                "process_owner",
            }:
                return candidate

        if isinstance(value, list):
            lowered = {str(item).strip().lower() for item in value if str(item).strip()}
            for claim in lowered:
                mapped = role_mapping.get(claim)
                if mapped:
                    return mapped

            if "system_admin" in lowered or "admin" in lowered:
                return "system_admin"
            if "audit_manager" in lowered:
                return "audit_manager"
            if "risk_manager" in lowered:
                return "risk_manager"
            if "compliance_officer" in lowered:
                return "compliance_officer"
            if "executive_viewer" in lowered:
                return "executive_viewer"
            if "external_auditor" in lowered:
                return "external_auditor"

    return settings.IDP_DEFAULT_ROLE


def _derive_org_id(payload: Dict[str, Any]) -> str:
    for key in settings.IDP_ORG_CLAIM_KEYS:
        value = payload.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return "default-org"


def validate_access_token(token: str) -> TokenClaims:
    """
    Validate bearer token against local issuer and (optionally) external IdPs.
    """
    payload = _decode_local_token(token)
    if payload is None:
        payload = _decode_external_token(token)

    if payload is None:
        raise JWTError("Token validation failed")

    username = _derive_username(payload)
    if not username:
        raise JWTError("Token missing subject identity")

    return TokenClaims(
        username=username,
        role=_derive_role(payload),
        org_id=_derive_org_id(payload),
        raw=payload,
    )
