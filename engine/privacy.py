"""PII anonymization utilities used by audit engines and report exports."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple


def tokenize_identities(findings: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Replace direct entity names with stable tokens (User_A, User_B, ...).

    Returns transformed findings and reverse map.
    """
    identity_map: Dict[str, str] = {}
    token_counter = 0

    def token_for(value: str) -> str:
        nonlocal token_counter
        if value not in identity_map:
            token_counter += 1
            suffix = chr(64 + ((token_counter - 1) % 26) + 1)
            identity_map[value] = f"User_{suffix}{(token_counter - 1) // 26 or ''}".rstrip()
        return identity_map[value]

    sanitized: List[Dict[str, Any]] = []
    for finding in findings:
        f = dict(finding)
        entity = str(f.get("entity") or "").strip()
        if entity:
            token = token_for(entity)
            f["entity"] = token
            if f.get("description"):
                f["description"] = re.sub(re.escape(entity), token, str(f["description"]))
            if f.get("detail"):
                f["detail"] = re.sub(re.escape(entity), token, str(f["detail"]))
        sanitized.append(f)

    reverse_map = {v: k for k, v in identity_map.items()}
    return sanitized, reverse_map
