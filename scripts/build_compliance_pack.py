"""
scripts/build_compliance_pack.py
Build a reproducible compliance evidence pack with checksums and zip bundle.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


EVIDENCE_FILE_PATTERNS = [
    "README.md",
    "docker-compose.yml",
    "alembic.ini",
    "alembic/versions/*.py",
    "core/config.py",
    "auth/token_validation.py",
    "api/v1/endpoints/system_logs.py",
    "monitoring/prometheus/*.yml",
    "monitoring/alertmanager/*.yml",
    "monitoring/otel-collector/*.yml",
    "monitoring/grafana/provisioning/datasources/*.yml",
    "monitoring/grafana/provisioning/dashboards/*.yml",
    "monitoring/grafana/dashboards/*.json",
    ".github/workflows/*.yml",
    "tests/test_*.py",
    "docs/*.md",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _collect_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    seen = set()
    for pattern in EVIDENCE_FILE_PATTERNS:
        for path in repo_root.glob(pattern):
            if path.is_file() and path not in seen:
                files.append(path)
                seen.add(path)
    files.sort(key=lambda p: str(p.relative_to(repo_root)))
    return files


def build_compliance_pack(output_root: Path | None = None) -> dict[str, str]:
    repo_root = Path(__file__).resolve().parents[1]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if output_root is None:
        output_root = repo_root / "artifacts"
    output_root.mkdir(parents=True, exist_ok=True)

    pack_dir = output_root / f"compliance-pack-{stamp}"
    pack_dir.mkdir(parents=True, exist_ok=True)

    evidence_files = _collect_files(repo_root)
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evidence_count": len(evidence_files),
        "files": [],
    }

    checksums_lines = []
    for file_path in evidence_files:
        rel = str(file_path.relative_to(repo_root))
        checksum = _sha256(file_path)
        manifest["files"].append({"path": rel, "sha256": checksum})
        checksums_lines.append(f"{checksum}  {rel}")

    manifest_path = pack_dir / "manifest.json"
    checksums_path = pack_dir / "checksums.sha256"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    checksums_path.write_text("\n".join(checksums_lines) + "\n", encoding="utf-8")

    zip_path = output_root / f"compliance-pack-{stamp}.zip"
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as zf:
        zf.write(manifest_path, arcname="manifest.json")
        zf.write(checksums_path, arcname="checksums.sha256")
        for file_path in evidence_files:
            rel = file_path.relative_to(repo_root)
            zf.write(file_path, arcname=str(rel))

    return {
        "pack_dir": str(pack_dir),
        "manifest": str(manifest_path),
        "checksums": str(checksums_path),
        "zip": str(zip_path),
    }


if __name__ == "__main__":
    result = build_compliance_pack()
    print(json.dumps(result, indent=2))
