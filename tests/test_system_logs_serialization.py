import unittest
from datetime import datetime, timezone
from uuid import uuid4

from api.v1.endpoints.system_logs import list_system_logs
from models.system_logs import SystemLog


class _FakeScalarResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _FakeExecResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return _FakeScalarResult(self._items)


class _FakeDB:
    def __init__(self, items):
        self._items = items

    async def execute(self, _query):
        return _FakeExecResult(self._items)


class TestSystemLogSerialization(unittest.IsolatedAsyncioTestCase):
    async def test_trace_span_ids_exposed(self):
        record = SystemLog(
            id=uuid4(),
            org_id="default-org",
            user="auditor",
            role="internal_auditor",
            action="data_access",
            resource="/api/v1/reports/kpis",
            method="GET",
            status_code=200,
            metadata_json={
                "request_id": "req-1",
                "trace_id": "abc123",
                "span_id": "def456",
            },
            immutable=True,
            created_at=datetime.now(timezone.utc),
        )
        db = _FakeDB([record])

        payload = await list_system_logs(limit=5, db=db, _=None)

        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["trace_id"], "abc123")
        self.assertEqual(payload[0]["span_id"], "def456")


if __name__ == "__main__":
    unittest.main()
