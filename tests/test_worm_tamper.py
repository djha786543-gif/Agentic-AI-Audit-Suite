import unittest
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException

from api.v1.endpoints import findings as findings_ep


class DummyDB:
    def __init__(self):
        self.committed = False

    async def commit(self):
        self.committed = True


class TestWormTamperBehavior(unittest.IsolatedAsyncioTestCase):
    async def test_delete_attempt_is_blocked_and_logged(self):
        called = {"logged": False}

        async def fake_append(db, **kwargs):
            called["logged"] = True

        original = findings_ep._append_worm_log
        findings_ep._append_worm_log = fake_append
        try:
            db = DummyDB()
            ctx = SimpleNamespace(org_id="default-org", username="admin")
            with self.assertRaises(HTTPException) as ex:
                await findings_ep.delete_finding_blocked(uuid4(), db=db, ctx=ctx)
            self.assertEqual(ex.exception.status_code, 409)
            self.assertTrue(called["logged"])
            self.assertTrue(db.committed)
        finally:
            findings_ep._append_worm_log = original


if __name__ == "__main__":
    unittest.main()
