# Compliance Evidence Pack

## Purpose
Produce a repeatable evidence artifact for audits, control attestations, and release sign-off.

## Command
- `make compliance-pack`
- Or directly: `python scripts/build_compliance_pack.py`

## Outputs
Generated under `artifacts/`:
- `compliance-pack-<timestamp>/manifest.json`
- `compliance-pack-<timestamp>/checksums.sha256`
- `compliance-pack-<timestamp>.zip`

## Contents
The pack includes key control evidence such as:
- Security/authentication configuration and token validation logic
- Monitoring and alerting configuration
- CI workflows and test files
- Migration configuration and baseline docs

## Integrity Verification
Use the SHA-256 checksums in `checksums.sha256` to verify included files.
