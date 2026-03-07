import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from api.v1.endpoints.system_logs import system_error_trace_groups
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


class TestSystemLogTraceGrouping(unittest.IsolatedAsyncioTestCase):
    async def test_error_logs_grouped_by_trace(self):
        now = datetime.now(timezone.utc)
        records = [
            SystemLog(
                id=uuid4(),
                org_id="default-org",
                user="u1",
                role="internal_auditor",
                action="data_access",
                resource="/api/v1/reports/kpis",
                method="GET",
                status_code=500,
                metadata_json={"trace_id": "trace-A", "span_id": "s1", "request_id": "req-1"},
                immutable=True,
                created_at=now,
            ),
            SystemLog(
                id=uuid4(),
                org_id="default-org",
                user="u1",
                role="internal_auditor",
                action="data_access",
                resource="/api/v1/reports/kpis",
                method="GET",
                status_code=502,
                metadata_json={"trace_id": "trace-A", "span_id": "s2", "request_id": "req-1"},
                immutable=True,
                created_at=now - timedelta(seconds=1),
            ),
            SystemLog(
                id=uuid4(),
                org_id="default-org",
                user="u2",
                role="audit_manager",
                action="data_access",
                resource="/api/v1/governance/risks",
                method="GET",
                status_code=404,
                metadata_json={"trace_id": "trace-B", "span_id": "s3", "request_id": "req-2"},
                immutable=True,
                created_at=now - timedelta(seconds=2),
            ),
        ]

        db = _FakeDB(records)
        payload = await system_error_trace_groups(limit=100, group_limit=10, db=db, _=None)

        self.assertEqual(payload["total_error_events"], 3)
        self.assertEqual(payload["total_trace_groups"], 2)
        first_group = payload["groups"][0]
        self.assertEqual(first_group["trace_id"], "trace-A")
        self.assertEqual(first_group["error_count"], 2)
        self.assertIn("req-1", first_group["request_ids"])

    async def test_filters_min_status_and_resource_prefix(self):
        now = datetime.now(timezone.utc)
        records = [
            SystemLog(
                id=uuid4(),
                org_id="default-org",
                user="u1",
                role="internal_auditor",
                action="data_access",
                resource="/api/v1/reports/kpis",
                method="GET",
                status_code=500,
                metadata_json={"trace_id": "trace-A", "request_id": "req-1"},
                immutable=True,
                created_at=now,
            ),
            SystemLog(
                id=uuid4(),
                org_id="default-org",
                user="u2",
                role="audit_manager",
                action="data_access",
                resource="/api/v1/governance/risks",
                method="GET",
                status_code=404,
                metadata_json={"trace_id": "trace-B", "request_id": "req-2"},
                immutable=True,
                created_at=now,
            ),
        ]

        db = _FakeDB(records)
        payload = await system_error_trace_groups(
            limit=100,
            group_limit=10,
            min_status=500,
            resource_prefix="/api/v1/reports",
            db=db,
            _=None,
        )

        self.assertEqual(payload["total_error_events"], 1)
        self.assertEqual(payload["total_trace_groups"], 1)
        self.assertEqual(payload["groups"][0]["trace_id"], "trace-A")

    async def test_filter_since_minutes(self):
        now = datetime.now(timezone.utc)
        records = [
            SystemLog(
                id=uuid4(),
                org_id="default-org",
                user="u1",
                role="internal_auditor",
                action="data_access",
                resource="/api/v1/reports/kpis",
                method="GET",
                status_code=500,
                metadata_json={"trace_id": "trace-now", "request_id": "req-1"},
                immutable=True,
                created_at=now,
            ),
            SystemLog(
                id=uuid4(),
                org_id="default-org",
                user="u1",
                role="internal_auditor",
                action="data_access",
                resource="/api/v1/reports/kpis",
                method="GET",
                status_code=500,
                metadata_json={"trace_id": "trace-old", "request_id": "req-2"},
                immutable=True,
                created_at=now - timedelta(minutes=120),
            ),
        ]

        db = _FakeDB(records)
        payload = await system_error_trace_groups(
            limit=100,
            group_limit=10,
            since_minutes=30,
            db=db,
            _=None,
        )

        self.assertEqual(payload["total_error_events"], 1)
        self.assertEqual(payload["total_trace_groups"], 1)
        self.assertEqual(payload["groups"][0]["trace_id"], "trace-now")

    async def test_sort_by_error_count_and_pagination(self):
        now = datetime.now(timezone.utc)
        records = [
            SystemLog(
                id=uuid4(),
                org_id="default-org",
                user="u1",
                role="internal_auditor",
                action="data_access",
                resource="/api/v1/reports/kpis",
                method="GET",
                status_code=500,
                metadata_json={"trace_id": "trace-A", "request_id": "req-1"},
                immutable=True,
                created_at=now,
            ),
            SystemLog(
                id=uuid4(),
                org_id="default-org",
                user="u1",
                role="internal_auditor",
                action="data_access",
                resource="/api/v1/reports/kpis",
                method="GET",
                status_code=500,
                metadata_json={"trace_id": "trace-A", "request_id": "req-1"},
                immutable=True,
                created_at=now - timedelta(seconds=1),
            ),
            SystemLog(
                id=uuid4(),
                org_id="default-org",
                user="u2",
                role="audit_manager",
                action="data_access",
                resource="/api/v1/governance/risks",
                method="GET",
                status_code=500,
                metadata_json={"trace_id": "trace-B", "request_id": "req-2"},
                immutable=True,
                created_at=now - timedelta(seconds=2),
            ),
            SystemLog(
                id=uuid4(),
                org_id="default-org",
                user="u3",
                role="audit_manager",
                action="data_access",
                resource="/api/v1/alerts",
                method="GET",
                status_code=500,
                metadata_json={"trace_id": "trace-C", "request_id": "req-3"},
                immutable=True,
                created_at=now - timedelta(seconds=3),
            ),
        ]

        db = _FakeDB(records)
        payload = await system_error_trace_groups(
            limit=200,
            group_limit=1,
            offset=1,
            sort_by="error_count",
            sort_order="desc",
            db=db,
            _=None,
        )

        self.assertEqual(payload["total_trace_groups"], 3)
        self.assertEqual(payload["returned_groups"], 1)
        # First page is trace-A (count=2); second page should be one of single-count groups.
        self.assertIn(payload["groups"][0]["trace_id"], {"trace-B", "trace-C"})

    async def test_event_limit_per_group_caps_payload(self):
        now = datetime.now(timezone.utc)
        records = [
            SystemLog(
                id=uuid4(),
                org_id="default-org",
                user="u1",
                role="internal_auditor",
                action="data_access",
                resource="/api/v1/reports/kpis",
                method="GET",
                status_code=500,
                metadata_json={"trace_id": "trace-A", "request_id": "req-1"},
                immutable=True,
                created_at=now,
            ),
            SystemLog(
                id=uuid4(),
                org_id="default-org",
                user="u1",
                role="internal_auditor",
                action="data_access",
                resource="/api/v1/reports/kpis",
                method="GET",
                status_code=500,
                metadata_json={"trace_id": "trace-A", "request_id": "req-1"},
                immutable=True,
                created_at=now - timedelta(seconds=1),
            ),
            SystemLog(
                id=uuid4(),
                org_id="default-org",
                user="u1",
                role="internal_auditor",
                action="data_access",
                resource="/api/v1/reports/kpis",
                method="GET",
                status_code=500,
                metadata_json={"trace_id": "trace-A", "request_id": "req-1"},
                immutable=True,
                created_at=now - timedelta(seconds=2),
            ),
        ]

        db = _FakeDB(records)
        payload = await system_error_trace_groups(
            limit=100,
            group_limit=10,
            event_limit_per_group=2,
            db=db,
            _=None,
        )

        self.assertEqual(payload["total_trace_groups"], 1)
        group = payload["groups"][0]
        self.assertEqual(group["error_count"], 3)
        self.assertEqual(group["total_events"], 3)
        self.assertEqual(group["returned_events"], 2)
        self.assertEqual(len(group["events"]), 2)

    async def test_include_event_fields_projects_payload(self):
        now = datetime.now(timezone.utc)
        records = [
            SystemLog(
                id=uuid4(),
                org_id="default-org",
                user="u1",
                role="internal_auditor",
                action="data_access",
                resource="/api/v1/reports/kpis",
                method="GET",
                status_code=500,
                metadata_json={"trace_id": "trace-A", "span_id": "s1", "request_id": "req-1"},
                immutable=True,
                created_at=now,
            ),
        ]

        db = _FakeDB(records)
        payload = await system_error_trace_groups(
            limit=100,
            group_limit=10,
            include_event_fields="status_code,resource,request_id,invalid_field",
            db=db,
            _=None,
        )

        event = payload["groups"][0]["events"][0]
        self.assertEqual(set(event.keys()), {"status_code", "resource", "request_id"})
        self.assertEqual(payload["paging"]["include_event_fields"], ["status_code", "resource", "request_id"])

    async def test_view_compact_projects_default_field_set(self):
        now = datetime.now(timezone.utc)
        records = [
            SystemLog(
                id=uuid4(),
                org_id="default-org",
                user="u1",
                role="internal_auditor",
                action="data_access",
                resource="/api/v1/reports/kpis",
                method="GET",
                status_code=500,
                metadata_json={"trace_id": "trace-A", "span_id": "s1", "request_id": "req-1"},
                immutable=True,
                created_at=now,
            ),
        ]

        db = _FakeDB(records)
        payload = await system_error_trace_groups(
            limit=100,
            group_limit=10,
            view="compact",
            db=db,
            _=None,
        )

        event = payload["groups"][0]["events"][0]
        self.assertEqual(
            set(event.keys()),
            {"status_code", "resource", "request_id", "created_at"},
        )
        self.assertEqual(payload["paging"]["view"], "compact")

    async def test_include_fields_override_view_preset(self):
        now = datetime.now(timezone.utc)
        records = [
            SystemLog(
                id=uuid4(),
                org_id="default-org",
                user="u1",
                role="internal_auditor",
                action="data_access",
                resource="/api/v1/reports/kpis",
                method="GET",
                status_code=500,
                metadata_json={"trace_id": "trace-A", "span_id": "s1", "request_id": "req-1"},
                immutable=True,
                created_at=now,
            ),
        ]

        db = _FakeDB(records)
        payload = await system_error_trace_groups(
            limit=100,
            group_limit=10,
            view="compact",
            include_event_fields="status_code,method",
            db=db,
            _=None,
        )

        event = payload["groups"][0]["events"][0]
        self.assertEqual(set(event.keys()), {"status_code", "method"})
        self.assertEqual(payload["paging"]["include_event_fields"], ["status_code", "method"])

    async def test_view_ids_returns_identifier_focused_payload(self):
        now = datetime.now(timezone.utc)
        records = [
            SystemLog(
                id=uuid4(),
                org_id="default-org",
                user="u1",
                role="internal_auditor",
                action="data_access",
                resource="/api/v1/reports/kpis",
                method="GET",
                status_code=500,
                metadata_json={"trace_id": "trace-A", "span_id": "s1", "request_id": "req-1"},
                immutable=True,
                created_at=now,
            ),
            SystemLog(
                id=uuid4(),
                org_id="default-org",
                user="u1",
                role="internal_auditor",
                action="data_access",
                resource="/api/v1/reports/kpis",
                method="GET",
                status_code=502,
                metadata_json={"trace_id": "trace-A", "span_id": "s2", "request_id": "req-2"},
                immutable=True,
                created_at=now - timedelta(seconds=1),
            ),
        ]

        db = _FakeDB(records)
        payload = await system_error_trace_groups(
            limit=100,
            group_limit=10,
            view="ids",
            db=db,
            _=None,
        )

        group = payload["groups"][0]
        event = group["events"][0]
        self.assertEqual(set(event.keys()), {"request_id", "span_id", "created_at"})
        self.assertEqual(payload["paging"]["view"], "ids")
        self.assertEqual(group["request_ids"], ["req-1", "req-2"])
        self.assertEqual(group["span_ids"], ["s1", "s2"])

    async def test_trace_id_prefix_filter(self):
        now = datetime.now(timezone.utc)
        records = [
            SystemLog(
                id=uuid4(),
                org_id="default-org",
                user="u1",
                role="internal_auditor",
                action="data_access",
                resource="/api/v1/reports/kpis",
                method="GET",
                status_code=500,
                metadata_json={"trace_id": "trace-abc-001", "span_id": "s1", "request_id": "req-1"},
                immutable=True,
                created_at=now,
            ),
            SystemLog(
                id=uuid4(),
                org_id="default-org",
                user="u1",
                role="internal_auditor",
                action="data_access",
                resource="/api/v1/reports/kpis",
                method="GET",
                status_code=500,
                metadata_json={"trace_id": "trace-xyz-002", "span_id": "s2", "request_id": "req-2"},
                immutable=True,
                created_at=now - timedelta(seconds=1),
            ),
        ]

        db = _FakeDB(records)
        payload = await system_error_trace_groups(
            limit=100,
            group_limit=10,
            trace_id_prefix="trace-abc",
            db=db,
            _=None,
        )

        self.assertEqual(payload["total_error_events"], 1)
        self.assertEqual(payload["groups"][0]["trace_id"], "trace-abc-001")

    async def test_request_id_prefix_filter(self):
        now = datetime.now(timezone.utc)
        records = [
            SystemLog(
                id=uuid4(),
                org_id="default-org",
                user="u1",
                role="internal_auditor",
                action="data_access",
                resource="/api/v1/reports/kpis",
                method="GET",
                status_code=500,
                metadata_json={"trace_id": "trace-1", "span_id": "s1", "request_id": "req-a-001"},
                immutable=True,
                created_at=now,
            ),
            SystemLog(
                id=uuid4(),
                org_id="default-org",
                user="u1",
                role="internal_auditor",
                action="data_access",
                resource="/api/v1/reports/kpis",
                method="GET",
                status_code=500,
                metadata_json={"trace_id": "trace-2", "span_id": "s2", "request_id": "req-b-002"},
                immutable=True,
                created_at=now - timedelta(seconds=1),
            ),
        ]

        db = _FakeDB(records)
        payload = await system_error_trace_groups(
            limit=100,
            group_limit=10,
            request_id_prefix="req-a",
            db=db,
            _=None,
        )

        self.assertEqual(payload["total_error_events"], 1)
        self.assertEqual(payload["groups"][0]["trace_id"], "trace-1")

    async def test_q_filter_matches_trace_resource_and_user(self):
        now = datetime.now(timezone.utc)
        records = [
            SystemLog(
                id=uuid4(),
                org_id="default-org",
                user="alice",
                role="internal_auditor",
                action="data_access",
                resource="/api/v1/reports/kpis",
                method="GET",
                status_code=500,
                metadata_json={"trace_id": "trace-alpha", "span_id": "s1", "request_id": "req-001"},
                immutable=True,
                created_at=now,
            ),
            SystemLog(
                id=uuid4(),
                org_id="default-org",
                user="bob",
                role="audit_manager",
                action="data_access",
                resource="/api/v1/governance/risks",
                method="GET",
                status_code=500,
                metadata_json={"trace_id": "trace-beta", "span_id": "s2", "request_id": "req-xyz"},
                immutable=True,
                created_at=now - timedelta(seconds=1),
            ),
        ]

        db = _FakeDB(records)

        by_trace = await system_error_trace_groups(limit=100, group_limit=10, q="alpha", db=db, _=None)
        self.assertEqual(by_trace["total_error_events"], 1)
        self.assertEqual(by_trace["groups"][0]["trace_id"], "trace-alpha")

        by_resource = await system_error_trace_groups(limit=100, group_limit=10, q="governance", db=db, _=None)
        self.assertEqual(by_resource["total_error_events"], 1)
        self.assertEqual(by_resource["groups"][0]["trace_id"], "trace-beta")

        by_user = await system_error_trace_groups(limit=100, group_limit=10, q="alice", db=db, _=None)
        self.assertEqual(by_user["total_error_events"], 1)
        self.assertEqual(by_user["groups"][0]["trace_id"], "trace-alpha")

    async def test_q_ranked_prioritizes_exact_trace_match(self):
        now = datetime.now(timezone.utc)
        records = [
            SystemLog(
                id=uuid4(),
                org_id="default-org",
                user="zara",
                role="audit_manager",
                action="data_access",
                resource="/api/v1/reports/kpis",
                method="GET",
                status_code=500,
                metadata_json={"trace_id": "trace-search", "span_id": "s1", "request_id": "req-1"},
                immutable=True,
                created_at=now - timedelta(minutes=5),
            ),
            SystemLog(
                id=uuid4(),
                org_id="default-org",
                user="alice",
                role="internal_auditor",
                action="data_access",
                resource="/api/v1/reports/searching/heavy",
                method="GET",
                status_code=500,
                metadata_json={"trace_id": "trace-other", "span_id": "s2", "request_id": "req-2"},
                immutable=True,
                created_at=now,
            ),
        ]

        db = _FakeDB(records)

        # Without ranking, newest record wins by default last_seen_at sort.
        default_sorted = await system_error_trace_groups(
            limit=100,
            group_limit=10,
            q="search",
            db=db,
            _=None,
        )
        self.assertEqual(default_sorted["groups"][0]["trace_id"], "trace-other")

        ranked = await system_error_trace_groups(
            limit=100,
            group_limit=10,
            q="search",
            q_ranked=True,
            db=db,
            _=None,
        )
        self.assertEqual(ranked["groups"][0]["trace_id"], "trace-search")
        self.assertTrue(ranked["filters"]["q_ranked"])


if __name__ == "__main__":
    unittest.main()
