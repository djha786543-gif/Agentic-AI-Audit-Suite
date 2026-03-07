from pathlib import Path


def test_prometheus_pack_files_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    assert (root / "monitoring" / "prometheus" / "prometheus.yml").exists()
    assert (root / "monitoring" / "prometheus" / "alerts.yml").exists()
    assert (root / "monitoring" / "prometheus" / "recording_rules.yml").exists()
    assert (root / "monitoring" / "alertmanager" / "alertmanager.yml").exists()
    assert (root / "monitoring" / "grafana" / "provisioning" / "datasources" / "prometheus.yml").exists()
    assert (root / "monitoring" / "grafana" / "provisioning" / "dashboards" / "dashboards.yml").exists()
    assert (root / "monitoring" / "grafana" / "dashboards" / "acap-overview.json").exists()
    assert (root / "monitoring" / "otel-collector" / "config.yml").exists()


def test_alert_rules_include_key_signals() -> None:
    root = Path(__file__).resolve().parents[1]
    alerts_text = (root / "monitoring" / "prometheus" / "alerts.yml").read_text(encoding="utf-8")

    required_alerts = [
        "AcapApiHigh5xxErrorRate",
        "AcapApiHighP95Latency",
        "AcapApiNoTraffic",
    ]
    for alert_name in required_alerts:
        assert alert_name in alerts_text

    assert "acap_http_requests_total" in alerts_text
    assert "acap_http_request_duration_seconds_bucket" in alerts_text


def test_prometheus_scrape_config_targets_metrics_endpoint() -> None:
    root = Path(__file__).resolve().parents[1]
    config_text = (root / "monitoring" / "prometheus" / "prometheus.yml").read_text(encoding="utf-8")

    assert "job_name: acap_api" in config_text
    assert "metrics_path: /metrics" in config_text
    assert "api:8000" in config_text
    assert "/etc/prometheus/recording_rules.yml" in config_text
    assert "job_name: otel_spanmetrics" in config_text
    assert "otel-collector:8889" in config_text


def test_prometheus_alerting_targets_alertmanager() -> None:
    root = Path(__file__).resolve().parents[1]
    config_text = (root / "monitoring" / "prometheus" / "prometheus.yml").read_text(encoding="utf-8")

    assert "alerting:" in config_text
    assert "alertmanagers:" in config_text
    assert "alertmanager:9093" in config_text


def test_alertmanager_receivers_present() -> None:
    root = Path(__file__).resolve().parents[1]
    am_text = (root / "monitoring" / "alertmanager" / "alertmanager.yml").read_text(encoding="utf-8")

    assert "receiver: webhook-default" in am_text
    assert "name: webhook-critical" in am_text
    assert "name: webhook-warning" in am_text
    assert "name: email-critical" in am_text
    assert "severity=\"critical\"" in am_text
    assert "severity=\"warning\"" in am_text


def test_recording_rules_include_slo_series() -> None:
    root = Path(__file__).resolve().parents[1]
    rules_text = (root / "monitoring" / "prometheus" / "recording_rules.yml").read_text(encoding="utf-8")

    required_series = [
        "acap:http_requests:availability5m",
        "acap:http_requests:error_ratio5m",
        "acap:http_requests:p95_latency_seconds5m",
        "acap:http_requests:p99_latency_seconds5m",
        "acap:traces:calls_rate5m",
        "acap:traces:error_ratio5m",
    ]
    for series in required_series:
        assert series in rules_text


def test_grafana_dashboard_contains_slo_queries() -> None:
    root = Path(__file__).resolve().parents[1]
    dashboard_text = (root / "monitoring" / "grafana" / "dashboards" / "acap-overview.json").read_text(encoding="utf-8")

    assert "ACAP Monitoring Overview" in dashboard_text
    assert "acap:http_requests:availability5m" in dashboard_text
    assert "acap:http_requests:error_ratio5m" in dashboard_text
    assert "acap:http_requests:p95_latency_seconds5m" in dashboard_text
    assert "acap:traces:calls_rate5m" in dashboard_text
    assert "acap:traces:error_ratio5m" in dashboard_text


def test_otel_collector_config_exposes_otlp_http() -> None:
    root = Path(__file__).resolve().parents[1]
    otel_text = (root / "monitoring" / "otel-collector" / "config.yml").read_text(encoding="utf-8")

    assert "receivers:" in otel_text
    assert "otlp:" in otel_text
    assert "endpoint: 0.0.0.0:4318" in otel_text
    assert "pipelines:" in otel_text
    assert "spanmetrics" in otel_text
    assert "endpoint: 0.0.0.0:8889" in otel_text
