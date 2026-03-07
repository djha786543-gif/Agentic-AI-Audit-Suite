import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_compliance_pack import build_compliance_pack


class TestCompliancePackBuilder(unittest.TestCase):
    def test_build_pack_outputs_manifest_and_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = build_compliance_pack(output_root=Path(tmp))

            manifest_path = Path(result["manifest"])
            checksums_path = Path(result["checksums"])
            zip_path = Path(result["zip"])

            self.assertTrue(manifest_path.exists())
            self.assertTrue(checksums_path.exists())
            self.assertTrue(zip_path.exists())

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertGreater(manifest["evidence_count"], 0)
            self.assertGreater(len(manifest["files"]), 0)


if __name__ == "__main__":
    unittest.main()
