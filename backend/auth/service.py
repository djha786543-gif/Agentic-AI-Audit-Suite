"""Auth adapter service.
Keeps auth behavior aligned with existing token validation.
"""
from __future__ import annotations

from auth.token_validation import TokenClaims, validate_access_token


def validate_token(token: str) -> TokenClaims:
    return validate_access_token(token)
