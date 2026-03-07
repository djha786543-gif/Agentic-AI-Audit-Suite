# SSO Claim Mapping Guide

## Goal
Map external IdP claims to ACAP internal authorization fields without code changes.

## Environment Variables
- `ENABLE_EXTERNAL_IDP_TOKENS`
- `IDP_ISSUERS`
- `IDP_AUDIENCES`
- `IDP_JWKS_URLS`
- `IDP_ROLE_CLAIM_KEYS`
- `IDP_ORG_CLAIM_KEYS`
- `IDP_ROLE_MAPPING`
- `IDP_DEFAULT_ROLE`

## Claim Mapping Behavior
1. ACAP checks each key in `IDP_ROLE_CLAIM_KEYS` in order.
2. For list-like claims (for example groups), each value is matched against `IDP_ROLE_MAPPING`.
3. For scalar role claims, exact value is matched in `IDP_ROLE_MAPPING`.
4. If no mapped role is found, `IDP_DEFAULT_ROLE` is used.
5. Organization/tenant is resolved from the first available key in `IDP_ORG_CLAIM_KEYS`.

## Example Configuration
```env
ENABLE_EXTERNAL_IDP_TOKENS=true
IDP_ISSUERS=https://login.microsoftonline.com/<tenant-id>/v2.0
IDP_AUDIENCES=api://acap-api
IDP_JWKS_URLS=https://login.microsoftonline.com/<tenant-id>/discovery/v2.0/keys

IDP_ROLE_CLAIM_KEYS=roles,groups,role
IDP_ORG_CLAIM_KEYS=org_id,tenant_id,tid
IDP_ROLE_MAPPING={"acap-audit-manager":"audit_manager","acap-admin":"system_admin"}
IDP_DEFAULT_ROLE=internal_auditor
```

## Validation
Run:
- `pytest -q tests/test_idp_claim_mapping.py`

This test verifies role mapping from external-style claims and fallback to default role.
