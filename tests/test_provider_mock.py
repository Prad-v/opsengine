"""Tests for the provider-mock service (run inside Docker via make mock-providers-test)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT_CANDIDATES = [
    Path(__file__).resolve().parents[1] / "backend" / "services" / "provider-mock",
    Path("/app"),
]
for _root in ROOT_CANDIDATES:
    if (_root / "app" / "main.py").exists() and str(_root) not in sys.path:
        sys.path.insert(0, str(_root))
        break

from app.main import app  # noqa: E402
from app.payloads import (  # noqa: E402
    PROVIDER_CATALOG,
    build_grafana_payload,
    build_mimir_payload,
    build_payload,
    build_victoriametrics_payload,
)


@pytest.fixture()
def client():
    return TestClient(app)


def test_health(client: TestClient):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_providers_catalog(client: TestClient):
    resp = client.get("/api/providers")
    assert resp.status_code == 200
    data = resp.json()
    keys = {p["key"] for p in data["providers"]}
    assert keys == {"grafana", "mimir", "victoriametrics", "temporal"}
    alert = next(p for p in data["providers"] if p["key"] == "grafana")
    temporal = next(p for p in data["providers"] if p["key"] == "temporal")
    assert alert["sample_payload"]["alerts"]
    assert alert["supports_events"] is True
    assert temporal["supports_events"] is False
    assert temporal["sample_payload"] is None
    assert data["defaults"]["temporal_address"]
    assert data["defaults"]["temporal_namespace"] == "default"


def test_temporal_auth_config_defaults():
    from app.main import _mock_auth_config

    auth = _mock_auth_config("temporal", "http://localhost:8099")
    assert auth["address"]
    assert auth["namespace"] == "default"
    assert auth["tls"] is False


def test_send_event_rejects_temporal(client: TestClient):
    resp = client.post(
        "/api/send-event",
        json={
            "provider": "temporal",
            "keep_api_url": "http://localhost:8080",
            "keep_api_key": "keepappkey",
        },
    )
    assert resp.status_code == 400


def test_grafana_mock_permissions(client: TestClient):
    resp = client.get("/grafana/api/access-control/user/permissions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["alert.rules:read"] is True
    assert body["alert.provisioning:write"] is True


def test_prometheus_mock_alerts(client: TestClient):
    resp = client.get("/prometheus/api/v1/alerts")
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"


def test_vmalert_mock_root(client: TestClient):
    resp = client.get("/vmalert/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_payload_builders_include_alerts():
    for builder in (
        build_grafana_payload,
        build_mimir_payload,
        build_victoriametrics_payload,
    ):
        payload = builder(status="firing")
        assert "alerts" in payload
        assert payload["alerts"][0]["labels"]["alertname"]
        assert payload["alerts"][0]["fingerprint"]


def test_build_payload_by_provider_key():
    from app.payloads import ALERT_PROVIDER_KEYS

    for key in ALERT_PROVIDER_KEYS:
        payload = build_payload(key, status="resolved", alertname="E2ETest")
        assert payload["status"] == "resolved"
        assert payload["alerts"][0]["labels"]["alertname"] == "E2ETest"


def test_build_payload_rejects_temporal():
    with pytest.raises(ValueError, match="Temporal"):
        build_payload("temporal")


def test_grafana_scenarios(client: TestClient):
    resp = client.get("/api/grafana/scenarios")
    assert resp.status_code == 200
    data = resp.json()
    ids = {s["id"] for s in data["scenarios"]}
    assert ids == {"cpu", "memory"}
    for s in data["scenarios"]:
        assert s["shared_labels"]["service"] == "payments-api"
        assert s["shared_labels"]["cluster"] == "mock-prod"
        assert s["payload"]["alerts"][0]["labels"]["alertname"]
    assert data["correlation_rule"]["threshold"] == 2
    assert "labels.service" in data["correlation_rule"]["groupingCriteria"]


def test_preview_grafana_scenario(client: TestClient):
    resp = client.post(
        "/api/preview-payload",
        json={
            "provider": "grafana",
            "scenario": "memory",
            "status": "firing",
            "keep_api_url": "http://localhost:8080",
            "keep_api_key": "keepappkey",
        },
    )
    assert resp.status_code == 200
    labels = resp.json()["payload"]["alerts"][0]["labels"]
    assert labels["alertname"] == "MockHighMemory"
    assert labels["severity"] == "critical"
    assert labels["service"] == "payments-api"


def test_ui_served(client: TestClient):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Provider Mock" in resp.text
    assert "Temporal" in resp.text
    assert 'data-tab="temporal"' in resp.text
