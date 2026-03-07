import unittest

from fastapi import FastAPI

from core.config import settings
from core.tracing import _normalize_otlp_endpoint, init_tracing


class TestTracingConfig(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_enabled = settings.ENABLE_OTEL_TRACING
        self._orig_endpoint = settings.OTEL_EXPORTER_OTLP_ENDPOINT

    def tearDown(self) -> None:
        settings.ENABLE_OTEL_TRACING = self._orig_enabled
        settings.OTEL_EXPORTER_OTLP_ENDPOINT = self._orig_endpoint

    def test_normalize_endpoint_appends_trace_path(self) -> None:
        endpoint = _normalize_otlp_endpoint("http://collector:4318")
        self.assertEqual(endpoint, "http://collector:4318/v1/traces")

    def test_normalize_endpoint_keeps_trace_path(self) -> None:
        endpoint = _normalize_otlp_endpoint("http://collector:4318/v1/traces")
        self.assertEqual(endpoint, "http://collector:4318/v1/traces")

    def test_init_tracing_noop_when_disabled(self) -> None:
        settings.ENABLE_OTEL_TRACING = False
        settings.OTEL_EXPORTER_OTLP_ENDPOINT = None
        app = FastAPI()

        init_tracing(app)


if __name__ == "__main__":
    unittest.main()
