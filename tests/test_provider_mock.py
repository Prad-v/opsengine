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
    assert data["defaults"]["netbox_url"]
    assert data["defaults"]["keep_netbox_url"]


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
        assert payload["alerts"][0]["labels"]["code"]
        assert payload["alerts"][0]["fingerprint"]
        assert payload["commonLabels"]["code"]


def test_payload_builders_use_reserved_codes():
    assert build_grafana_payload()["alerts"][0]["labels"]["code"] == "HIGH_CPU"
    assert build_mimir_payload()["alerts"][0]["labels"]["code"] == "DISK_SPACE_LOW"
    assert (
        build_victoriametrics_payload()["alerts"][0]["labels"]["code"] == "HIGH_MEMORY"
    )


def test_correlation_rules_filter_on_labels_code():
    from app.payloads import GRAFANA_CORRELATION_RULE, GRAFANA_GPU_CORRELATION_RULE

    assert "labels.code" in GRAFANA_CORRELATION_RULE["celQuery"]
    assert "HIGH_CPU" in GRAFANA_CORRELATION_RULE["celQuery"]
    assert "HIGH_MEMORY" in GRAFANA_CORRELATION_RULE["celQuery"]
    assert "labels.code" in GRAFANA_GPU_CORRELATION_RULE["celQuery"]
    assert "NVIDIA_GPU" in GRAFANA_GPU_CORRELATION_RULE["celQuery"]


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
    assert {"cpu", "memory"}.issubset(ids)
    assert {
        "gpu_temp",
        "gpu_mem",
        "gpu_xid",
        "gpu_ecc",
        "gpu_throttle",
        "gpu_nvlink",
        "gpu_power",
        "gpu_unavailable",
    }.issubset(ids)

    payments = [s for s in data["scenarios"] if s.get("pack") == "payments"]
    assert len(payments) == 2
    for s in payments:
        assert s["shared_labels"]["service"] == "payments-api"
        assert s["shared_labels"]["cluster"] == "mock-prod"
        assert s["payload"]["alerts"][0]["labels"]["alertname"]
        assert s["payload"]["alerts"][0]["labels"]["code"]
        assert s["shared_labels"]["code"]

    gpu = [s for s in data["scenarios"] if s.get("pack") == "nvidia-gpu"]
    assert len(gpu) == 8
    hosts = set()
    for s in gpu:
        assert s["shared_labels"]["cluster"] == "ai-dc-prod"
        assert s["shared_labels"]["region"] == "us-west-2"
        assert s["shared_labels"]["datacenter"] == "ai-dc-1"
        assert s["shared_labels"]["row"]
        assert s["shared_labels"]["rack"]
        assert s["shared_labels"]["gpu_id"]
        hosts.add(s["shared_labels"]["host"])
        labels = s["payload"]["alerts"][0]["labels"]
        assert labels["vendor"] == "nvidia"
        assert labels["gpu_model"].startswith("NVIDIA-")
        assert labels["dcgm_field"]
        assert labels["code"].startswith("NVIDIA_GPU_")
        assert labels["row"]
        assert labels["rack"]
        assert labels["gpu_id"].startswith(labels["host"])
    assert "gpu-node-a03" in hosts
    assert len(hosts) >= 2

    assert data["correlation_rule"]["threshold"] == 2
    assert "labels.service" in data["correlation_rule"]["groupingCriteria"]
    assert "labels.code" in data["correlation_rule"]["celQuery"]
    assert "HIGH_CPU" in data["correlation_rule"]["celQuery"]
    assert data["gpu_correlation_rule"]["incidentPrefix"] == "GPU"
    assert "labels.host" in data["gpu_correlation_rule"]["groupingCriteria"]
    assert "labels.code" in data["gpu_correlation_rule"]["celQuery"]
    assert "NVIDIA_GPU" in data["gpu_correlation_rule"]["celQuery"]
    assert data["packs"]["nvidia-gpu"]["demo_scenario_ids"] == ["gpu_temp", "gpu_mem"]


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
    assert labels["code"] == "HIGH_MEMORY"


def test_preview_grafana_gpu_scenario(client: TestClient):
    resp = client.post(
        "/api/preview-payload",
        json={
            "provider": "grafana",
            "scenario": "gpu_temp",
            "status": "firing",
            "keep_api_url": "http://localhost:8080",
            "keep_api_key": "keepappkey",
        },
    )
    assert resp.status_code == 200
    body = resp.json()["payload"]
    labels = body["alerts"][0]["labels"]
    assert labels["alertname"] == "NvidiaGpuHighTemperature"
    assert labels["severity"] == "critical"
    assert labels["cluster"] == "ai-dc-prod"
    assert labels["vendor"] == "nvidia"
    assert labels["dcgm_field"] == "DCGM_FI_DEV_GPU_TEMP"
    assert labels["code"] == "NVIDIA_GPU_THERMAL"
    assert labels["region"] == "us-west-2"
    assert labels["datacenter"] == "ai-dc-1"
    assert labels["row"] == "row-a"
    assert labels["rack"] == "rack-12"
    assert labels["gpu"] == "0"
    assert labels["gpu_id"] == "gpu-node-a03-gpu0"
    assert body["alerts"][0]["values"]["B"] == 91.0
    assert body["commonLabels"]["vendor"] == "nvidia"


def test_build_all_gpu_scenarios():
    from app.payloads import GRAFANA_GPU_SCENARIOS, build_grafana_scenario_payload

    for scenario_id in GRAFANA_GPU_SCENARIOS:
        payload = build_grafana_scenario_payload(scenario_id, status="firing")
        alert = payload["alerts"][0]
        assert alert["labels"]["alertname"].startswith("Nvidia")
        assert alert["labels"]["datacenter"] == "ai-dc-1"
        assert alert["labels"]["region"] == "us-west-2"
        assert alert["labels"]["row"]
        assert alert["labels"]["rack"]
        assert alert["labels"]["gpu_id"]
        assert alert["labels"]["code"].startswith("NVIDIA_GPU_")
        assert alert["fingerprint"]


def test_ui_served(client: TestClient):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Provider Mock" in resp.text
    assert "Temporal" in resp.text
    assert 'data-tab="temporal"' in resp.text
    assert "gpu_temp" in resp.text
    assert "sendGpuGrafana" in resp.text
    assert "NVIDIA GPU" in resp.text
    assert 'data-tab="gpu"' in resp.text
    assert 'data-tab="topology"' in resp.text
    assert "topoPush" in resp.text
    assert "topoExportMock" in resp.text
    assert "topoImportKeep" in resp.text
    assert "netboxConfigureKeep" in resp.text
    assert "Configure Keep with NetBox" in resp.text


def test_gpu_server_remediate_and_email(client: TestClient):
    reset = client.post("/api/gpu/server/reset")
    assert reset.status_code == 200

    snap = client.get("/api/gpu/server")
    assert snap.status_code == 200
    body = snap.json()
    assert body["force_fail"] is False
    assert body["server"]["host"] == "gpu-node-a03"
    assert body["server"]["gpu_model"].startswith("NVIDIA-")
    assert body["server"]["region"] == "us-west-2"
    assert body["server"]["row"] == "row-a"
    assert body["server"]["rack"] == "rack-12"
    assert len(body["server"]["gpus"]) >= 2
    assert len(body["nodes"]) >= 3

    ok = client.post(
        "/api/gpu/server/remediate",
        json={"action": "reset_gpu", "gpu_index": 0, "incident_id": "inc-1"},
    )
    assert ok.status_code == 200
    assert ok.json()["ok"] is True

    mode = client.post("/api/gpu/server/mode", json={"force_fail": True})
    assert mode.status_code == 200
    assert mode.json()["force_fail"] is True

    fail = client.post(
        "/api/gpu/server/remediate",
        json={"action": "reset_gpu", "gpu_index": 0, "incident_id": "inc-2"},
    )
    assert fail.status_code == 503
    detail = fail.json()["detail"]
    assert detail["ok"] is False

    mail = client.post(
        "/api/gpu/emails",
        json={
            "to": "ops@ai-dc.local",
            "subject": "GPU fail",
            "body": "remediation failed",
            "incident_id": "inc-2",
        },
    )
    assert mail.status_code == 200
    assert mail.json()["ok"] is True

    inbox = client.get("/api/gpu/emails")
    assert inbox.status_code == 200
    assert len(inbox.json()["emails"]) >= 1
    assert inbox.json()["emails"][0]["subject"] == "GPU fail"

    other = client.post(
        "/api/gpu/server/mode",
        json={"force_fail": False},
    )
    assert other.status_code == 200
    other_ok = client.post(
        "/api/gpu/server/remediate",
        json={
            "action": "reset_gpu",
            "gpu_index": 1,
            "host": "gpu-node-a01",
            "incident_id": "inc-3",
        },
    )
    assert other_ok.status_code == 200
    assert other_ok.json()["host"] == "gpu-node-a01"
    assert other_ok.json()["rack"] == "rack-11"


def test_gpu_topology_inventory(client: TestClient):
    resp = client.get("/api/gpu/topology")
    assert resp.status_code == 200
    body = resp.json()
    summary = body["summary"]
    assert summary["region"] == "us-west-2"
    assert summary["datacenter"] == "ai-dc-1"
    assert "row-a" in summary["rows"]
    assert "rack-12" in summary["racks"]
    assert "gpu-node-a03-gpu0" in summary["gpu_ids"]
    keep = body["keep"]
    names = {svc["service"] for svc in keep["services"]}
    assert {
        "us-west-2",
        "ai-dc-1",
        "row-a",
        "rack-12",
        "gpu-node-a03",
        "gpu-node-a03-gpu0",
        "gpu-inference",
    }.issubset(names)
    yaml_doc = body["yaml"]
    assert len(yaml_doc["services"]) == len(keep["services"])
    assert yaml_doc["applications"][0]["name"] == "NVIDIA GPU Inference"
    assert "gpu-inference" in body["yaml_text"]
    alias = client.get("/api/topology")
    assert alias.status_code == 200
    assert alias.json()["summary"]["region"] == "us-west-2"


def test_topology_export_yaml(client: TestClient):
    resp = client.get("/api/topology/export")
    assert resp.status_code == 200
    assert "yaml" in resp.headers.get("content-type", "")
    text = resp.text
    assert "us-west-2" in text
    assert "gpu-node-a03-gpu0" in text
    assert "NVIDIA GPU Inference" in text


def test_topology_import_rejects_invalid_yaml(client: TestClient):
    resp = client.post(
        "/api/topology/keep/import",
        json={
            "keep_api_url": "http://localhost:8080",
            "keep_api_key": "keepappkey",
            "yaml": "just a string",
        },
    )
    assert resp.status_code == 400


def test_parse_topology_document_roundtrip():
    from app.gpu_topology import parse_topology_document, topology_yaml_text

    text = topology_yaml_text()
    parsed = parse_topology_document(text)
    assert parsed["services"]
    assert parsed["applications"][0]["name"] == "NVIDIA GPU Inference"
    as_json = __import__("json").dumps(
        {"services": [{"id": 1, "service": "demo", "display_name": "Demo"}]}
    )
    json_doc = parse_topology_document(as_json)
    assert json_doc["services"][0]["service"] == "demo"


def test_gpu_push_topology_applies_keep_spec(client: TestClient):
    from app.gpu_topology import apply_keep_topology, build_keep_topology_spec

    spec = build_keep_topology_spec()
    store = {"services": {}, "deps": [], "apps": []}

    def request_fn(method, path, body=None):
        if method == "GET" and path.startswith("/topology/applications"):
            return 200, store["apps"]
        if method == "GET" and path.startswith("/topology"):
            rows = []
            for name, svc in store["services"].items():
                deps = [
                    {"serviceId": dst, "protocol": proto}
                    for src, dst, proto in store["deps"]
                    if src == svc["id"]
                ]
                rows.append({**svc, "service": name, "dependencies": deps})
            return 200, rows
        if method == "POST" and path == "/topology/service":
            sid = len(store["services"]) + 1
            store["services"][body["service"]] = {**body, "id": sid}
            return 201, store["services"][body["service"]]
        if method == "POST" and path == "/topology/dependency":
            store["deps"].append(
                (body["service_id"], body["depends_on_service_id"], body["protocol"])
            )
            return 201, {"id": len(store["deps"])}
        if method == "POST" and path == "/topology/applications":
            store["apps"].append(body)
            return 201, body
        if method == "PUT" and path.startswith("/topology/applications/"):
            app_id = path.rsplit("/", 1)[-1]
            for index, app in enumerate(store["apps"]):
                if str(app.get("id")) == app_id or app.get("name") == body.get("name"):
                    store["apps"][index] = {**app, **body, "id": app.get("id") or app_id}
                    return 200, store["apps"][index]
            return 404, {"error": "not found"}
        if method == "DELETE" and path.startswith("/topology/applications/"):
            app_id = path.rsplit("/", 1)[-1]
            store["apps"] = [
                app for app in store["apps"] if str(app.get("id")) != app_id
            ]
            return 200, {"ok": True}
        return 500, {"error": path}

    result = apply_keep_topology(request_fn)
    assert result["ok"] is True
    assert len(result["services_created"]) == len(spec["services"])
    assert result["application_created"] is True
    # Second apply is idempotent.
    again = apply_keep_topology(request_fn)
    assert again["services_created"] == []
    assert again["dependencies_created"] == 0
    assert again["application_created"] is False
    assert "gpu-node-a03-gpu0" in store["services"]
    assert any(app["name"] == "NVIDIA GPU Inference" for app in store["apps"])
    assert len(store["apps"]) == 1

    store["apps"].append(
        {"id": "dup-1", "name": "NVIDIA GPU Inference", "services": []}
    )
    store["apps"].append(
        {"id": "dup-2", "name": "NVIDIA GPU Inference", "services": []}
    )
    collapsed = apply_keep_topology(request_fn)
    assert collapsed["application_created"] is False
    assert len(store["apps"]) == 1
    assert store["apps"][0]["name"] == "NVIDIA GPU Inference"


def test_topology_keep_import_and_export_proxy(client: TestClient, monkeypatch):
    from app import main as mock_main

    calls = []

    def fake_keep_call(**kwargs):
        calls.append(kwargs)
        path = kwargs["path"]
        if path == "/topology/import":
            return 200, {"message": "Topology imported successfully"}
        if path == "/topology/export":
            return 200, "applications: []\nservices: []\ndependencies: []\n"
        if path.startswith("/topology/applications"):
            return 200, [{"name": "NVIDIA GPU Inference"}]
        if path.startswith("/topology"):
            return 200, [
                {"id": "1", "service": "gpu-inference", "dependencies": []},
                {"id": "2", "service": "gpu-node-a03", "dependencies": []},
            ]
        return 404, {"detail": path}

    monkeypatch.setattr(mock_main, "_keep_call", fake_keep_call)

    yaml_text = client.get("/api/topology/export").text
    imported = client.post(
        "/api/topology/keep/import",
        json={
            "keep_api_url": "http://localhost:8080",
            "keep_api_key": "keepappkey",
            "yaml": yaml_text,
        },
    )
    assert imported.status_code == 200
    body = imported.json()
    assert body["ok"] is True
    assert body["services"] >= 1
    assert any(c["path"] == "/topology/import" for c in calls)

    exported = client.get(
        "/api/topology/keep/export",
        params={
            "keep_api_url": "http://localhost:8080",
            "keep_api_key": "keepappkey",
        },
    )
    assert exported.status_code == 200
    assert "services:" in exported.json()["yaml"]

    status = client.get(
        "/api/topology/keep",
        params={
            "keep_api_url": "http://localhost:8080",
            "keep_api_key": "keepappkey",
        },
    )
    assert status.status_code == 200
    summary = status.json()
    assert summary["has_nvidia_gpu"] is True
    assert summary["service_count"] == 2


def test_netbox_dcim_plan_matches_mock_topology():
    from app.netbox_dcim import build_dcim_plan

    plan = build_dcim_plan()
    assert plan["region"]["slug"] == "us-west-2"
    assert plan["site"]["slug"] == "ai-dc-1"
    assert {row["slug"] for row in plan["rows"]} == {"row-a", "row-b"}
    assert {rack["name"] for rack in plan["racks"]} == {"rack-11", "rack-12", "rack-21"}
    hosts = {host["name"]: host for host in plan["hosts"]}
    assert hosts["gpu-node-a03"]["rack"] == "rack-12"
    assert hosts["gpu-node-a03"]["ip"] == "10.12.0.13/24"
    gpu_ids = {gpu["gpu_id"] for host in plan["hosts"] for gpu in host["gpus"]}
    assert "gpu-node-a03-gpu0" in gpu_ids
    assert plan["prefix"]["prefix"] == "10.12.0.0/24"
    assert plan["vlan"]["vid"] == 100


class _FakeNetBox:
    def __init__(self):
        self.collections: dict[str, list[dict]] = {}
        self.next_id = 1

    def request(self, method, url, headers, json_body, params):
        from urllib.parse import urlparse

        path = urlparse(url).path
        if method == "GET" and path.rstrip("/").endswith("/api/status"):
            return 200, {"netbox-version": "4.2.9"}
        items = self.collections.setdefault(path, [])
        if method == "GET":

            def _matches(obj: dict) -> bool:
                for key, value in (params or {}).items():
                    if key.endswith("_id"):
                        field = key[:-3]
                        if str(obj.get(field)) != str(value) and str(obj.get(key)) != str(
                            value
                        ):
                            return False
                    elif str(obj.get(key)) != str(value):
                        return False
                return True

            return 200, {"count": 0, "next": None, "results": [i for i in items if _matches(i)]}
        if method == "POST":
            obj = {**(json_body or {}), "id": self.next_id}
            self.next_id += 1
            items.append(obj)
            return 201, obj
        if method == "PATCH":
            return 200, json_body or {}
        return 404, {"detail": "not found"}


def test_seed_nvidia_dcim_is_idempotent():
    from app.netbox_dcim import NetBoxClient, seed_nvidia_dcim

    fake = _FakeNetBox()
    client = NetBoxClient(
        "http://netbox:8080",
        "token",
        request_fn=fake.request,
    )
    first = seed_nvidia_dcim(client)
    second = seed_nvidia_dcim(client)
    assert first["counts"]["hosts"] == 3
    assert first["counts"]["gpus"] == 6
    assert first["counts"]["racks"] == 3
    assert second["counts"]["hosts"] == 3
    assert len(fake.collections["/api/dcim/devices/"]) == 3


def test_netbox_seed_and_configure_keep(client: TestClient, monkeypatch):
    from app.netbox_dcim import NetBoxClient
    from app import main as mock_main

    fake = _FakeNetBox()

    def fake_client(*args, **kwargs):
        url = args[0] if args else kwargs.get("base_url", "http://netbox:8080")
        token = args[1] if len(args) > 1 else kwargs.get("token", "token")
        return NetBoxClient(url, token, request_fn=fake.request)

    monkeypatch.setattr(mock_main, "NetBoxClient", fake_client)

    calls = []

    def fake_keep_call(**kwargs):
        calls.append(kwargs)
        path = kwargs["path"]
        if path == "/providers" and kwargs["method"] == "GET":
            return 200, {"installed_providers": []}
        if path == "/providers/install":
            return 200, {"id": "netbox-provider-1", "type": "netbox"}
        if path.startswith("/topology/pull"):
            return 200, [{"service": "gpu-node-a03"}]
        return 404, {"detail": path}

    monkeypatch.setattr(mock_main, "_keep_call", fake_keep_call)

    seed = client.post("/api/netbox/seed", json={})
    assert seed.status_code == 200
    assert seed.json()["counts"]["gpus"] == 6

    configured = client.post(
        "/api/netbox/configure-keep",
        json={
            "keep_api_url": "http://localhost:8080",
            "keep_api_key": "keepappkey",
            "seed": True,
            "pull": True,
        },
    )
    assert configured.status_code == 200
    body = configured.json()
    assert body["ok"] is True
    assert body["provider_id"] == "netbox-provider-1"
    assert any(c["path"] == "/providers/install" for c in calls)
    assert any(str(c["path"]).startswith("/topology/pull") for c in calls)


def test_netbox_status_when_unreachable(client: TestClient, monkeypatch):
    from app import main as mock_main
    from app.netbox_dcim import NetBoxClient, NetBoxError

    def boom(*args, **kwargs):
        client_obj = NetBoxClient("http://netbox:8080", "token")

        def fail(*_a, **_k):
            raise NetBoxError(502, "connection refused")

        client_obj.request = fail  # type: ignore[method-assign]
        return client_obj

    monkeypatch.setattr(mock_main, "_netbox_client", boom)
    resp = client.get("/api/netbox/status")
    assert resp.status_code == 200
    assert resp.json()["ok"] is False
    assert resp.json()["plan"]["site"] == "ai-dc-1"


def test_find_installed_netbox_matches_details_name_not_uuid():
    from app.netbox_dcim import NETBOX_PROVIDER_NAME, find_installed_netbox

    uuid_id = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
    found = find_installed_netbox(
        [
            {
                "id": uuid_id,
                "type": "netbox",
                "display_name": "NetBox",
                "details": {"name": NETBOX_PROVIDER_NAME},
            }
        ]
    )
    assert found is not None
    assert found["id"] == uuid_id
    assert (
        find_installed_netbox(
            [
                {
                    "id": uuid_id,
                    "type": "grafana",
                    "details": {"name": NETBOX_PROVIDER_NAME},
                }
            ]
        )
        is None
    )
    named = find_installed_netbox(
        [
            {"id": "other", "type": "netbox", "details": {"name": "other-netbox"}},
            {
                "id": "wanted",
                "type": "netbox",
                "details": {"name": NETBOX_PROVIDER_NAME},
            },
        ]
    )
    assert named is not None
    assert named["id"] == "wanted"
    fallback = find_installed_netbox(
        [{"id": "only", "type": "netbox", "display_name": "NetBox"}]
    )
    assert fallback is not None
    assert fallback["id"] == "only"


def test_ai_dc_synth_catalog_and_probes(client: TestClient):
    from app.synth_probes import GOLDEN_COMPLETION, synth_probes

    synth_probes.reset()
    catalog = client.get("/api/synth")
    assert catalog.status_code == 200
    probes = catalog.json()["probes"]
    ids = {p["id"] for p in probes}
    assert {
        "nvidia-dcgm",
        "nvidia-inference-golden",
        "amd-rocm",
        "amd-inference-golden",
        "nvidia-nccl",
        "amd-rccl",
        "training-submit",
        "training-checkpoint",
        "storage-health",
    }.issubset(ids)

    dcgm = client.get("/api/synth/nvidia/dcgm/metrics")
    assert dcgm.status_code == 200
    assert "DCGM_FI_DEV_GPU_TEMP" in dcgm.text

    nvml = client.get("/api/synth/nvidia/nvml")
    assert nvml.status_code == 200
    assert nvml.json()["device_count"] == 8

    golden = client.post("/api/synth/nvidia/inference/v1/chat/completions", json={})
    assert golden.status_code == 200
    assert GOLDEN_COMPLETION in golden.json()["choices"][0]["message"]["content"]

    amd = client.get("/api/synth/amd/rocm")
    assert amd.json()["vendor"] == "amd"
    assert amd.json()["device_count"] == 8

    job = client.post("/api/synth/training/submit", json={"gpus": 1})
    assert job.json()["state"] == "Running"

    fail = client.post(
        "/api/synth/fail",
        json={"probe_id": "nvidia-inference-health", "failed": True},
    )
    assert fail.status_code == 200
    unhealthy = client.get("/api/synth/nvidia/inference/health")
    assert unhealthy.status_code == 503

    client.post("/api/synth/fail", json={"probe_id": "nvidia-dcgm", "failed": True})
    dcgm_fail = client.get("/api/synth/nvidia/dcgm/metrics")
    assert dcgm_fail.status_code == 200
    assert "DCGM_FI_DEV_GPU_TEMP" not in dcgm_fail.text

    client.post("/api/synth/fail", json={"probe_id": "training-submit", "failed": True})
    pending = client.post("/api/synth/training/submit", json={})
    assert pending.json()["state"] == "Pending"

    reset = client.post("/api/synth/reset")
    assert reset.status_code == 200
    recovered = client.get("/api/synth/nvidia/inference/health")
    assert recovered.status_code == 200
    assert recovered.json()["ok"] is True


def test_ai_dc_synth_index_has_tab():
    html = None
    for candidate in (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "services"
        / "provider-mock"
        / "app"
        / "static"
        / "index.html",
        Path("/app/app/static/index.html"),
    ):
        if candidate.exists():
            html = candidate
            break
    assert html is not None
    text = html.read_text()
    assert 'data-tab="synth"' in text
    assert "AI datacenter synthetic probes" in text



