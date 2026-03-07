import unittest

from engine.runner import run_audit_engine


class TestTier1RunnerBehavior(unittest.TestCase):
    def test_lineage_attached_to_findings(self):
        parsed = {
            "sheets": {
                "users": {
                    "data_type": "users",
                    "records": [
                        {
                            "user_id": "u100",
                            "status": "active",
                            "roles": "create_vendor;pay_vendor",
                            "_lineage": {"source_type": "csv", "row_number": 2, "erp_table": "active_users"},
                        }
                    ],
                }
            },
            "total_records": 1,
        }
        result = run_audit_engine(parsed, source_system="UnitTest")
        self.assertGreaterEqual(result["total_findings"], 1)
        first = result["all_findings"][0]
        self.assertIn("evidence", first)
        self.assertIn("lineage", first["evidence"])
        self.assertEqual(first["evidence"]["lineage"].get("row_number"), 2)

    def test_integrity_blocks_sod_when_hr_mismatch(self):
        parsed = {
            "sheets": {
                "users": {
                    "data_type": "users",
                    "records": [
                        {
                            "user_id": "missing_hr_user",
                            "status": "active",
                            "roles": "create_vendor;pay_vendor",
                            "_lineage": {"source_type": "csv", "row_number": 2},
                        }
                    ],
                },
                "hr": {
                    "data_type": "hr_master",
                    "records": [
                        {
                            "user_id": "different_user",
                            "_lineage": {"source_type": "csv", "row_number": 2},
                        }
                    ],
                },
            },
            "total_records": 2,
        }
        result = run_audit_engine(parsed, source_system="UnitTest")
        self.assertIn("referential_integrity", result["domain_results"])
        self.assertFalse(result["domain_results"]["referential_integrity"]["summary"]["pass"])
        self.assertTrue(result["domain_results"]["sod"]["summary"].get("blocked"))


if __name__ == "__main__":
    unittest.main()
