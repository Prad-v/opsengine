"""Mock alert sources with UI for Grafana, Mimir Alertmanager, and VictoriaMetrics."""

from __future__ import annotations

import os
import time
from collections import deque
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urljoin

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, HttpUrl

from app.gpu_server import gpu_server
from app.synth_probes import (
    handle_amd_rocm,
    handle_checkpoint,
    handle_collective,
    handle_golden_prompt,
    handle_inference_health,
    handle_inference_ready,
    handle_netbox,
    handle_nvidia_dcgm,
    handle_nvidia_nvml,
    handle_storage,
    handle_training_submit,
    synth_probes,
)
from app.gpu_topology import (
    apply_keep_topology,
    build_keep_topology_spec,
    build_keep_topology_yaml_dict,
    parse_topology_document,
    topology_summary,
    topology_yaml_text,
)
from app.netbox_dcim import (
    DEFAULT_TOKEN,
    NETBOX_PROVIDER_NAME,
    NetBoxClient,
    NetBoxError,
    build_dcim_plan,
    find_installed_netbox,
    seed_nvidia_dcim,
)
from app.payloads import (
    GRAFANA_CORRELATION_RULE,
    GRAFANA_GPU_CORRELATION_RULE,
    GRAFANA_GPU_DEMO_SCENARIO_IDS,
    GRAFANA_GPU_SCENARIOS,
    GRAFANA_PAYMENTS_SCENARIOS,
    GRAFANA_SCENARIOS,
    PROVIDER_CATALOG,
    ProviderKey,
    build_grafana_scenario_payload,
    build_payload,
)

STATIC_DIR = Path(__file__).parent / "static"
DEFAULT_KEEP_API_URL = os.environ.get("KEEP_API_URL", "http://host.docker.internal:8080")
DEFAULT_KEEP_API_KEY = os.environ.get("KEEP_API_KEY", "keepappkey")
# Keep hybrid API runs on the host, so it must reach the published mock port via localhost.
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8099").rstrip("/")
# Temporal docker-compose frontend as seen by host Keep (`make start`).
DEFAULT_TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
DEFAULT_TEMPORAL_NAMESPACE = os.environ.get("TEMPORAL_NAMESPACE", "default")
DEFAULT_TEMPORAL_TLS = os.environ.get("TEMPORAL_TLS", "false").lower() in (
    "1",
    "true",
    "yes",
)
DEFAULT_TEMPORAL_UI_URL = os.environ.get(
    "TEMPORAL_UI_URL", "http://localhost:8233"
).rstrip("/")
DEFAULT_NETBOX_URL = os.environ.get("NETBOX_URL", "http://netbox:8080").rstrip("/")
DEFAULT_KEEP_NETBOX_URL = os.environ.get(
    "KEEP_NETBOX_URL", "http://localhost:8000"
).rstrip("/")
DEFAULT_NETBOX_TOKEN = os.environ.get("NETBOX_API_TOKEN", DEFAULT_TOKEN)
PORT = int(os.environ.get("PORT", "8099"))

# In-memory registry of providers installed into Keep via this mock.
_registry: dict[ProviderKey, dict[str, Any]] = {}
_event_log: deque[dict[str, Any]] = deque(maxlen=100)

app = FastAPI(
    title="Keep Provider Mock",
    description=(
        "Mock Grafana / Mimir Alertmanager / VictoriaMetrics webhooks "
        "(including NVIDIA GPU / AI datacenter scenarios), "
        "plus Temporal provider registration against local Docker Compose Temporal, "
        "NVIDIA GPU Service Topology import/export, NetBox DCIM seed/configure, "
        "and AI-datacenter synthetic probe endpoints (NVIDIA/AMD inference + training)"
    ),
    version="1.5.0",
)


class KeepConnection(BaseModel):
    keep_api_url: HttpUrl = Field(default=DEFAULT_KEEP_API_URL)
    keep_api_key: str = Field(default=DEFAULT_KEEP_API_KEY, min_length=1)


class RegisterRequest(KeepConnection):
    provider: ProviderKey
    provider_name: str | None = None
    public_base_url: HttpUrl | None = None
    temporal_address: str | None = None
    temporal_namespace: str | None = None
    temporal_tls: bool | None = None


class SendEventRequest(KeepConnection):
    provider: ProviderKey
    status: Literal["firing", "resolved"] = "firing"
    alertname: str | None = None
    severity: str | None = None
    provider_id: str | None = None
    payload: dict[str, Any] | None = None
    use_linked: bool = False
    scenario: str | None = None


class GrafanaIncidentDemoRequest(KeepConnection):
    """Create correlation rule (if missing) and send Grafana mock payloads."""

    provider_id: str | None = None
    create_rule: bool = True
    status: Literal["firing", "resolved"] = "firing"
    # When True, fire every NVIDIA GPU scenario (not just the default pair).
    send_all_gpu: bool = False


class GpuRemediateRequest(BaseModel):
    action: str = "reset_gpu"
    gpu_index: int = 0
    incident_id: str | None = None
    alertname: str | None = None
    host: str | None = None


class GpuModeRequest(BaseModel):
    force_fail: bool = False


class SynthFailRequest(BaseModel):
    probe_id: str | None = None
    failed: bool | dict[str, bool] | None = None


class GpuEmailRequest(BaseModel):
    to: str = "ops@ai-dc.local"
    subject: str
    body: str
    incident_id: str | None = None
    metadata: dict[str, Any] | None = None


class GpuPushTopologyRequest(KeepConnection):
    pass


class TopologyYamlBody(KeepConnection):
    yaml: str = Field(min_length=1)


class NetBoxSeedRequest(BaseModel):
    netbox_url: str | None = None
    api_token: str | None = None
    verify_ssl: bool = False


class NetBoxConfigureKeepRequest(KeepConnection, NetBoxSeedRequest):
    keep_netbox_url: str | None = None
    provider_name: str = NETBOX_PROVIDER_NAME
    seed: bool = True
    pull: bool = True
    pulling_enabled: bool = True


def _log(entry: dict[str, Any]) -> None:
    entry["ts"] = time.time()
    _event_log.appendleft(entry)


def _keep_headers(api_key: str, *, json_content: bool = True) -> dict[str, str]:
    headers = {
        "X-API-KEY": api_key,
        "Accept": "application/json",
    }
    if json_content:
        headers["Content-Type"] = "application/json"
    return headers


def _keep_call(
    *,
    keep_base: str,
    api_key: str,
    method: str,
    path: str,
    json_body: dict[str, Any] | None = None,
    files: dict[str, Any] | None = None,
    accept: str = "application/json",
    timeout: float = 30.0,
) -> tuple[int, Any]:
    url = f"{keep_base.rstrip('/')}{path}"
    headers = {"X-API-KEY": api_key, "Accept": accept}
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.request(
                method,
                url,
                headers=headers,
                json=json_body if files is None else None,
                files=files,
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502, detail=f"Failed to reach Keep API: {exc}"
        ) from exc
    body: Any
    content_type = resp.headers.get("content-type", "")
    if "yaml" in content_type or path.endswith("/export"):
        body = resp.text
    else:
        try:
            body = resp.json()
        except Exception:
            body = resp.text
    return resp.status_code, body


def _mock_auth_config(
    provider: ProviderKey,
    public_base: str,
    *,
    temporal_address: str | None = None,
    temporal_namespace: str | None = None,
    temporal_tls: bool | None = None,
) -> dict[str, Any]:
    if provider == "grafana":
        return {
            "token": "mock-grafana-token",
            "host": f"{public_base}/grafana",
        }
    if provider == "mimir":
        return {
            "url": f"{public_base}/prometheus",
            "verify": False,
        }
    if provider == "victoriametrics":
        return {
            "VMAlertURL": f"{public_base}/vmalert",
            "SkipValidation": True,
        }
    if provider == "temporal":
        return {
            "address": temporal_address or DEFAULT_TEMPORAL_ADDRESS,
            "namespace": temporal_namespace or DEFAULT_TEMPORAL_NAMESPACE,
            "tls": DEFAULT_TEMPORAL_TLS if temporal_tls is None else temporal_tls,
        }
    raise ValueError(provider)


# ---------------------------------------------------------------------------
# Mock backends Keep talks to during provider install / pull
# ---------------------------------------------------------------------------


@app.get("/grafana/api/health")
async def grafana_health() -> dict[str, Any]:
    return {"database": "ok", "version": "11.2.0", "commit": "mock"}


@app.get("/grafana/api/access-control/user/permissions")
async def grafana_permissions() -> dict[str, bool]:
    return {
        "alert.rules:read": True,
        "alert.provisioning:read": True,
        "alert.provisioning:write": True,
    }


@app.get("/prometheus/api/v1/alerts")
async def prometheus_alerts() -> dict[str, Any]:
    return {"status": "success", "data": {"alerts": []}}


@app.get("/prometheus/api/v1/query")
async def prometheus_query(query: str = "") -> dict[str, Any]:
    return {
        "status": "success",
        "data": {"resultType": "vector", "result": []},
    }


@app.get("/vmalert/")
@app.get("/vmalert")
async def vmalert_root() -> dict[str, str]:
    return {"status": "ok", "service": "mock-vmalert"}


@app.get("/vmalert/api/v1/alerts")
async def vmalert_alerts() -> dict[str, Any]:
    return {"status": "success", "data": {"alerts": []}}


# ---------------------------------------------------------------------------
# Mock control plane API
# ---------------------------------------------------------------------------


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def _synth_http(status: int, body: dict[str, Any] | str, media: str) -> Response:
    if isinstance(body, dict):
        return JSONResponse(status_code=status, content=body)
    return Response(status_code=status, content=body, media_type=media)


# ---------------------------------------------------------------------------
# AI datacenter synthetic probes (Keep Catalog → Synthetic checks)
# ---------------------------------------------------------------------------


@app.get("/api/synth")
async def get_synth_catalog() -> dict[str, Any]:
    return synth_probes.snapshot()


@app.post("/api/synth/fail")
async def set_synth_fail(body: SynthFailRequest) -> dict[str, Any]:
    if isinstance(body.failed, dict):
        result = synth_probes.set_failed_many(body.failed)
        _log({"action": "synth-fail", "ok": True, "failed": result["failed"]})
        return result
    if not body.probe_id:
        raise HTTPException(status_code=400, detail="probe_id is required")
    failed = True if body.failed is None else bool(body.failed)
    result = synth_probes.set_failed(body.probe_id, failed)
    _log({"action": "synth-fail", "ok": True, "probe_id": body.probe_id, "failed": failed})
    return result


@app.post("/api/synth/reset")
async def reset_synth_probes() -> dict[str, Any]:
    result = synth_probes.reset()
    _log({"action": "synth-reset", "ok": True})
    return result


@app.get("/api/synth/nvidia/dcgm/metrics")
async def synth_nvidia_dcgm() -> Response:
    return _synth_http(*handle_nvidia_dcgm())


@app.get("/api/synth/nvidia/nvml")
async def synth_nvidia_nvml() -> Response:
    return _synth_http(*handle_nvidia_nvml())


@app.get("/api/synth/nvidia/inference/health")
async def synth_nvidia_inference_health() -> Response:
    return _synth_http(*handle_inference_health("nvidia-inference-health", "nvidia"))


@app.get("/api/synth/nvidia/inference/v2/health/ready")
async def synth_nvidia_inference_ready() -> Response:
    return _synth_http(*handle_inference_ready())


@app.post("/api/synth/nvidia/inference/v1/chat/completions")
async def synth_nvidia_golden() -> Response:
    return _synth_http(*handle_golden_prompt("nvidia-inference-golden", "nvidia"))


@app.get("/api/synth/nvidia/nccl/allreduce")
async def synth_nvidia_nccl() -> Response:
    return _synth_http(*handle_collective("nvidia-nccl", "nvidia", "nccl"))


@app.get("/api/synth/amd/rocm")
async def synth_amd_rocm() -> Response:
    return _synth_http(*handle_amd_rocm())


@app.get("/api/synth/amd/inference/health")
async def synth_amd_inference_health() -> Response:
    return _synth_http(*handle_inference_health("amd-inference-health", "amd"))


@app.post("/api/synth/amd/inference/v1/chat/completions")
async def synth_amd_golden() -> Response:
    return _synth_http(*handle_golden_prompt("amd-inference-golden", "amd"))


@app.get("/api/synth/amd/rccl/allreduce")
async def synth_amd_rccl() -> Response:
    return _synth_http(*handle_collective("amd-rccl", "amd", "rccl"))


@app.post("/api/synth/training/submit")
async def synth_training_submit() -> Response:
    return _synth_http(*handle_training_submit())


@app.post("/api/synth/training/checkpoint")
async def synth_training_checkpoint() -> Response:
    return _synth_http(*handle_checkpoint())


@app.get("/api/synth/storage/health")
async def synth_storage() -> Response:
    return _synth_http(*handle_storage())


@app.get("/api/synth/netbox/health")
async def synth_netbox() -> Response:
    return _synth_http(*handle_netbox())


# ---------------------------------------------------------------------------
# Mock NVIDIA GPU server (Temporal remediations target)
# ---------------------------------------------------------------------------


@app.get("/gpu/server")
@app.get("/api/gpu/server")
async def get_gpu_server() -> dict[str, Any]:
    return gpu_server.snapshot()


@app.post("/gpu/server/mode")
@app.post("/api/gpu/server/mode")
async def set_gpu_mode(body: GpuModeRequest) -> dict[str, Any]:
    result = gpu_server.set_mode(force_fail=body.force_fail)
    _log({"action": "gpu-mode", "ok": True, "force_fail": body.force_fail})
    return result


@app.post("/gpu/server/remediate")
@app.post("/api/gpu/server/remediate")
async def remediate_gpu(body: GpuRemediateRequest) -> dict[str, Any]:
    result = gpu_server.remediate(
        action=body.action,
        gpu_index=body.gpu_index,
        incident_id=body.incident_id,
        alertname=body.alertname,
        host=body.host,
    )
    _log(
        {
            "action": "gpu-remediate",
            "ok": result.get("ok"),
            "incident_id": body.incident_id,
            "error": result.get("error"),
        }
    )
    if not result.get("ok"):
        raise HTTPException(status_code=503, detail=result)
    return result


@app.get("/gpu/emails")
@app.get("/api/gpu/emails")
async def list_gpu_emails() -> dict[str, Any]:
    return {"emails": list(gpu_server.emails)}


@app.post("/gpu/emails")
@app.post("/api/gpu/emails")
async def create_gpu_email(body: GpuEmailRequest) -> dict[str, Any]:
    mail = gpu_server.add_email(
        to=body.to,
        subject=body.subject,
        body=body.body,
        incident_id=body.incident_id,
        metadata=body.metadata,
    )
    _log(
        {
            "action": "gpu-email",
            "ok": True,
            "incident_id": body.incident_id,
            "subject": body.subject,
        }
    )
    return {"ok": True, "email": mail}


@app.delete("/gpu/emails")
@app.delete("/api/gpu/emails")
async def clear_gpu_emails() -> dict[str, Any]:
    gpu_server.clear_emails()
    return {"ok": True}


@app.post("/gpu/server/reset")
@app.post("/api/gpu/server/reset")
async def reset_gpu_server() -> dict[str, Any]:
    return gpu_server.reset()


@app.get("/gpu/topology")
@app.get("/api/gpu/topology")
@app.get("/api/topology")
async def get_gpu_topology() -> dict[str, Any]:
    """NVIDIA region/datacenter/row/rack/GPU inventory + Keep topology spec."""
    yaml_doc = build_keep_topology_yaml_dict()
    return {
        "summary": topology_summary(),
        "nodes": gpu_server.snapshot()["nodes"],
        "keep": build_keep_topology_spec(),
        "yaml": yaml_doc,
        "yaml_text": topology_yaml_text(yaml_doc),
    }


@app.get("/gpu/topology/export")
@app.get("/api/gpu/topology/export")
@app.get("/api/topology/export")
async def export_mock_topology_yaml() -> Response:
    """Download the NVIDIA GPU topology as Keep import YAML."""
    body = topology_yaml_text()
    return Response(
        content=body,
        media_type="application/x-yaml",
        headers={
            "Content-Disposition": "attachment; filename=nvidia-gpu-datacenter.yml"
        },
    )


@app.post("/gpu/topology/push")
@app.post("/api/gpu/push-topology")
@app.post("/api/topology/push")
async def push_gpu_topology(body: GpuPushTopologyRequest) -> dict[str, Any]:
    """Idempotently create the NVIDIA topology in Keep (REST, no wipe)."""
    keep_base = str(body.keep_api_url).rstrip("/")

    def request_fn(method: str, path: str, payload: dict[str, Any] | None = None):
        status, parsed = _keep_call(
            keep_base=keep_base,
            api_key=body.keep_api_key,
            method=method,
            path=path,
            json_body=payload,
        )
        return status, parsed

    try:
        result = apply_keep_topology(request_fn)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    _log({"action": "gpu-push-topology", "ok": True, **result})
    return result


@app.get("/api/topology/keep")
async def get_keep_topology(
    keep_api_url: str = DEFAULT_KEEP_API_URL,
    keep_api_key: str = DEFAULT_KEEP_API_KEY,
) -> dict[str, Any]:
    """Read current Keep Service Topology via the Keep API."""
    keep_base = keep_api_url.rstrip("/")
    svc_status, services = _keep_call(
        keep_base=keep_base,
        api_key=keep_api_key,
        method="GET",
        path="/topology?include_empty_deps=true",
    )
    if svc_status >= 400:
        raise HTTPException(status_code=svc_status, detail=services)
    app_status, applications = _keep_call(
        keep_base=keep_base,
        api_key=keep_api_key,
        method="GET",
        path="/topology/applications",
    )
    if app_status >= 400:
        applications = []
    service_rows = services if isinstance(services, list) else []
    app_rows = applications if isinstance(applications, list) else []
    names = [
        item.get("service")
        for item in service_rows
        if isinstance(item, dict) and item.get("service")
    ]
    return {
        "ok": True,
        "keep_api_url": keep_base,
        "service_count": len(service_rows),
        "application_count": len(app_rows),
        "services": names,
        "applications": [
            item.get("name")
            for item in app_rows
            if isinstance(item, dict) and item.get("name")
        ],
        "has_nvidia_gpu": bool(
            {"gpu-inference", "gpu-node-a03", "us-west-2"} & set(names)
        ),
    }


@app.get("/api/topology/keep/export")
async def export_keep_topology(
    keep_api_url: str = DEFAULT_KEEP_API_URL,
    keep_api_key: str = DEFAULT_KEEP_API_KEY,
    download: bool = False,
) -> Any:
    """Export Keep's current topology YAML (proxied GET /topology/export)."""
    keep_base = keep_api_url.rstrip("/")
    status, body = _keep_call(
        keep_base=keep_base,
        api_key=keep_api_key,
        method="GET",
        path="/topology/export",
        accept="application/x-yaml",
    )
    if status >= 400:
        raise HTTPException(status_code=status, detail=body)
    yaml_text = body if isinstance(body, str) else str(body)
    if download:
        return Response(
            content=yaml_text,
            media_type="application/x-yaml",
            headers={
                "Content-Disposition": "attachment; filename=keep-topology.yml"
            },
        )
    return {"ok": True, "yaml": yaml_text, "bytes": len(yaml_text.encode("utf-8"))}


@app.post("/api/topology/keep/import")
async def import_keep_topology(body: TopologyYamlBody) -> dict[str, Any]:
    """Replace Keep topology from YAML/JSON in the request body (Keep POST /topology/import)."""
    try:
        parsed = parse_topology_document(body.yaml)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    yaml_text = topology_yaml_text(parsed)
    keep_base = str(body.keep_api_url).rstrip("/")
    status, result = _keep_call(
        keep_base=keep_base,
        api_key=body.keep_api_key,
        method="POST",
        path="/topology/import",
        files={
            "file": (
                "topology.yml",
                yaml_text.encode("utf-8"),
                "application/x-yaml",
            )
        },
        accept="application/json",
    )
    if status >= 400:
        raise HTTPException(status_code=status, detail=result)
    _log(
        {
            "action": "topology-import",
            "ok": True,
            "services": len(parsed.get("services") or []),
        }
    )
    return {
        "ok": True,
        "message": "Topology imported into Keep",
        "services": len(parsed.get("services") or []),
        "dependencies": len(parsed.get("dependencies") or []),
        "applications": len(parsed.get("applications") or []),
        "keep": result,
    }


def _netbox_client(
    *,
    netbox_url: str | None = None,
    api_token: str | None = None,
    verify_ssl: bool = False,
) -> NetBoxClient:
    return NetBoxClient(
        netbox_url or DEFAULT_NETBOX_URL,
        api_token or DEFAULT_NETBOX_TOKEN,
        verify=verify_ssl,
    )


@app.get("/api/netbox/status")
async def netbox_status(
    netbox_url: str | None = None,
    api_token: str | None = None,
) -> dict[str, Any]:
    """Reachability of the compose NetBox API."""
    client = _netbox_client(netbox_url=netbox_url, api_token=api_token)
    try:
        status = client.status()
    except NetBoxError as exc:
        status = {
            "ok": False,
            "status_code": exc.status,
            "body": exc.detail,
            "url": client.base_url,
        }
    plan = build_dcim_plan()
    return {
        **status,
        "keep_netbox_url": DEFAULT_KEEP_NETBOX_URL,
        "provider_name": NETBOX_PROVIDER_NAME,
        "plan": {
            "region": plan["region"]["slug"],
            "site": plan["site"]["slug"],
            "rows": [row["slug"] for row in plan["rows"]],
            "racks": [rack["name"] for rack in plan["racks"]],
            "hosts": [host["name"] for host in plan["hosts"]],
            "prefix": plan["prefix"]["prefix"],
        },
    }


@app.post("/api/netbox/seed")
async def netbox_seed(body: NetBoxSeedRequest) -> dict[str, Any]:
    """Create the NVIDIA GPU DCIM/IPAM objects in NetBox (idempotent)."""
    client = _netbox_client(
        netbox_url=body.netbox_url,
        api_token=body.api_token,
        verify_ssl=body.verify_ssl,
    )
    try:
        seeded = seed_nvidia_dcim(client)
    except NetBoxError as exc:
        _log(
            {
                "action": "netbox-seed",
                "ok": False,
                "status_code": exc.status,
                "error": str(exc.detail)[:500],
            }
        )
        raise HTTPException(
            status_code=502,
            detail=f"NetBox seed failed ({exc.status}): {exc.detail}",
        ) from exc
    _log({"action": "netbox-seed", "ok": True, **seeded.get("counts", {})})
    return {"ok": True, **seeded}


@app.post("/api/netbox/configure-keep")
async def netbox_configure_keep(body: NetBoxConfigureKeepRequest) -> dict[str, Any]:
    """Seed NetBox, install the Keep NetBox provider, and pull topology."""
    seed_result: dict[str, Any] | None = None
    if body.seed:
        seed_result = await netbox_seed(
            NetBoxSeedRequest(
                netbox_url=body.netbox_url,
                api_token=body.api_token,
                verify_ssl=body.verify_ssl,
            )
        )

    keep_base = str(body.keep_api_url).rstrip("/")
    keep_netbox_url = (body.keep_netbox_url or DEFAULT_KEEP_NETBOX_URL).rstrip("/")
    token = body.api_token or DEFAULT_NETBOX_TOKEN
    provider_name = body.provider_name or NETBOX_PROVIDER_NAME

    status, providers_payload = _keep_call(
        keep_base=keep_base,
        api_key=body.keep_api_key,
        method="GET",
        path="/providers",
    )
    if status >= 400:
        raise HTTPException(status_code=status, detail=providers_payload)
    installed = []
    if isinstance(providers_payload, dict):
        installed = providers_payload.get("installed_providers") or []
    elif isinstance(providers_payload, list):
        installed = providers_payload
    existing = find_installed_netbox(installed, provider_name=provider_name)

    install_result: Any = None
    provider_id = existing.get("id") if existing else None
    if not provider_id:
        install_status, install_result = _keep_call(
            keep_base=keep_base,
            api_key=body.keep_api_key,
            method="POST",
            path="/providers/install",
            json_body={
                "provider_id": "netbox",
                "provider_name": provider_name,
                "provider_type": "netbox",
                "pulling_enabled": body.pulling_enabled,
                "netbox_url": keep_netbox_url,
                "api_token": token,
                "verify_ssl": body.verify_ssl,
            },
        )
        if install_status == 409:
            status, providers_payload = _keep_call(
                keep_base=keep_base,
                api_key=body.keep_api_key,
                method="GET",
                path="/providers",
            )
            installed = (
                (providers_payload or {}).get("installed_providers")
                if isinstance(providers_payload, dict)
                else []
            )
            existing = find_installed_netbox(installed, provider_name=provider_name)
            provider_id = existing.get("id") if existing else None
            install_result = {"action": "exists", "provider": existing}
        elif install_status >= 400:
            raise HTTPException(status_code=install_status, detail=install_result)
        else:
            provider_id = (install_result or {}).get("id") if isinstance(install_result, dict) else None
            if isinstance(install_result, dict):
                install_result = {"action": "created", **install_result}
    else:
        install_result = {"action": "exists", "id": provider_id}

    pull_result: Any = None
    if body.pull and provider_id:
        pull_status, pull_result = _keep_call(
            keep_base=keep_base,
            api_key=body.keep_api_key,
            method="POST",
            path=f"/topology/pull?provider_ids={provider_id}",
            timeout=120.0,
        )
        if pull_status >= 400:
            raise HTTPException(status_code=pull_status, detail=pull_result)

    _log(
        {
            "action": "netbox-configure-keep",
            "ok": True,
            "provider_id": provider_id,
            "keep_netbox_url": keep_netbox_url,
        }
    )
    return {
        "ok": True,
        "provider_id": provider_id,
        "provider_name": provider_name,
        "keep_netbox_url": keep_netbox_url,
        "seed": seed_result,
        "install": install_result,
        "pull": {"ok": True, "result": pull_result} if body.pull else None,
    }


@app.get("/api/providers")
async def list_providers() -> dict[str, Any]:
    items = []
    for key, meta in PROVIDER_CATALOG.items():
        registered = _registry.get(key)
        sample_payload = None
        if meta.get("supports_events"):
            sample_payload = build_payload(key, status="firing")
        items.append(
            {
                "key": key,
                **meta,
                "registered": registered is not None,
                "registration": registered,
                "sample_payload": sample_payload,
            }
        )
    return {
        "providers": items,
        "defaults": {
            "keep_api_url": DEFAULT_KEEP_API_URL,
            "keep_api_key": DEFAULT_KEEP_API_KEY,
            "public_base_url": PUBLIC_BASE_URL,
            "temporal_address": DEFAULT_TEMPORAL_ADDRESS,
            "temporal_namespace": DEFAULT_TEMPORAL_NAMESPACE,
            "temporal_tls": DEFAULT_TEMPORAL_TLS,
            "temporal_ui_url": DEFAULT_TEMPORAL_UI_URL,
            "netbox_url": DEFAULT_NETBOX_URL,
            "keep_netbox_url": DEFAULT_KEEP_NETBOX_URL,
            "netbox_api_token": DEFAULT_NETBOX_TOKEN,
            "netbox_provider_name": NETBOX_PROVIDER_NAME,
        },
    }


@app.get("/api/registry")
async def get_registry() -> dict[str, Any]:
    return {"registry": _registry}


@app.get("/api/events")
async def get_events() -> dict[str, Any]:
    return {"events": list(_event_log)}


@app.get("/api/grafana/scenarios")
async def grafana_scenarios() -> dict[str, Any]:
    scenarios = []
    for item in GRAFANA_SCENARIOS.values():
        payload = build_grafana_scenario_payload(item["id"], status="firing")
        kwargs = item["builder_kwargs"]
        scenarios.append(
            {
                **{k: item[k] for k in ("id", "label", "description", "pack") if k in item},
                "shared_labels": {
                    "service": kwargs["service"],
                    "cluster": kwargs["cluster"],
                    "host": kwargs["host"],
                    "code": payload["alerts"][0]["labels"].get("code"),
                    "region": payload["alerts"][0]["labels"].get("region"),
                    "datacenter": payload["alerts"][0]["labels"].get("datacenter"),
                    "row": payload["alerts"][0]["labels"].get("row"),
                    "rack": payload["alerts"][0]["labels"].get("rack"),
                    "gpu": payload["alerts"][0]["labels"].get("gpu"),
                    "gpu_id": payload["alerts"][0]["labels"].get("gpu_id"),
                },
                "payload": payload,
            }
        )
    return {
        "scenarios": scenarios,
        "packs": {
            "payments": {
                "scenario_ids": list(GRAFANA_PAYMENTS_SCENARIOS),
                "correlation_rule": GRAFANA_CORRELATION_RULE,
                "demo_scenario_ids": ["cpu", "memory"],
            },
            "nvidia-gpu": {
                "scenario_ids": list(GRAFANA_GPU_SCENARIOS),
                "correlation_rule": GRAFANA_GPU_CORRELATION_RULE,
                "demo_scenario_ids": list(GRAFANA_GPU_DEMO_SCENARIO_IDS),
            },
        },
        "correlation_rule": GRAFANA_CORRELATION_RULE,
        "gpu_correlation_rule": GRAFANA_GPU_CORRELATION_RULE,
        "ui_hint": {
            "source_filter_value": "grafana",
            "group_by": "labels.service",
            "threshold": 2,
            "cel": GRAFANA_CORRELATION_RULE["celQuery"],
            "gpu_group_by": "labels.host",
            "gpu_cel": GRAFANA_GPU_CORRELATION_RULE["celQuery"],
        },
    }


async def _ensure_correlation_rule(
    *,
    keep_base: str,
    headers: dict[str, str],
    rule: dict[str, Any],
) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            existing = await client.get(f"{keep_base}/rules", headers=headers)
            if existing.status_code >= 400:
                raise HTTPException(
                    status_code=existing.status_code, detail=existing.text
                )
            rules = existing.json()
            found = next(
                (
                    r
                    for r in rules
                    if (r.get("name") or r.get("ruleName")) == rule["ruleName"]
                ),
                None,
            )
            if found:
                return {"action": "exists", "rule": found}
            created = await client.post(
                f"{keep_base}/rules",
                headers=headers,
                json=rule,
            )
            if created.status_code >= 400:
                try:
                    detail = created.json()
                except Exception:
                    detail = created.text
                raise HTTPException(status_code=created.status_code, detail=detail)
            _log(
                {
                    "action": "create-rule",
                    "provider": "grafana",
                    "ok": True,
                    "rule": rule["ruleName"],
                }
            )
            return {"action": "created", "rule": created.json()}
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502, detail=f"Failed to manage correlation rule: {exc}"
        ) from exc


async def _send_grafana_scenarios(
    *,
    keep_base: str,
    headers: dict[str, str],
    provider_id: str | None,
    scenario_ids: tuple[str, ...] | list[str],
    status: str,
    run_id: str,
) -> list[dict[str, Any]]:
    import asyncio

    send_results = []
    for idx, scenario_id in enumerate(scenario_ids):
        # Space out sends so Keep's async event workers don't race two incidents
        # for the same grouping fingerprint.
        if idx > 0:
            await asyncio.sleep(4)
        payload = build_grafana_scenario_payload(
            scenario_id, status=status, run_id=run_id
        )
        path = "alerts/event/grafana"
        query = f"?provider_id={provider_id}" if provider_id else ""
        url = urljoin(keep_base + "/", path) + query
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            _log(
                {
                    "action": "send-event",
                    "provider": "grafana",
                    "ok": False,
                    "error": str(exc),
                    "scenario": scenario_id,
                }
            )
            raise HTTPException(
                status_code=502, detail=f"Failed to send {scenario_id} event: {exc}"
            ) from exc
        try:
            response_body: Any = resp.json()
        except Exception:
            response_body = resp.text
        ok = resp.status_code < 400
        _log(
            {
                "action": "send-event",
                "provider": "grafana",
                "ok": ok,
                "status_code": resp.status_code,
                "scenario": scenario_id,
                "payload_alertname": payload["alerts"][0]["labels"]["alertname"],
                "provider_id": provider_id,
                "run_id": run_id,
            }
        )
        if not ok:
            raise HTTPException(status_code=resp.status_code, detail=response_body)
        send_results.append(
            {
                "scenario": scenario_id,
                "status_code": resp.status_code,
                "response": response_body,
                "alertname": payload["alerts"][0]["labels"]["alertname"],
            }
        )
    return send_results


@app.post("/api/grafana/create-incident-demo")
async def grafana_create_incident_demo(
    body: GrafanaIncidentDemoRequest,
) -> dict[str, Any]:
    """Ensure the payments correlation rule exists, then fire payload A + B."""
    import uuid as uuid_mod

    keep_base = str(body.keep_api_url).rstrip("/")
    headers = _keep_headers(body.keep_api_key)
    rule_result: dict[str, Any] | None = None
    run_id = uuid_mod.uuid4().hex[:8]

    if body.create_rule:
        rule_result = await _ensure_correlation_rule(
            keep_base=keep_base,
            headers=headers,
            rule=GRAFANA_CORRELATION_RULE,
        )

    provider_id = body.provider_id or (_registry.get("grafana") or {}).get(
        "keep_provider_id"
    )
    send_results = await _send_grafana_scenarios(
        keep_base=keep_base,
        headers=headers,
        provider_id=provider_id,
        scenario_ids=("cpu", "memory"),
        status=body.status,
        run_id=run_id,
    )

    return {
        "ok": True,
        "run_id": run_id,
        "correlation_rule": rule_result,
        "events": send_results,
        "next_steps": (
            "Open Keep → Incidents. After both alerts are processed, look for "
            f"'{GRAFANA_CORRELATION_RULE['incidentPrefix']}' / payments degradation "
            "(threshold=2, group by labels.service)."
        ),
    }


@app.post("/api/grafana/create-gpu-incident-demo")
async def grafana_create_gpu_incident_demo(
    body: GrafanaIncidentDemoRequest,
) -> dict[str, Any]:
    """Ensure the NVIDIA GPU correlation rule exists, then fire GPU mock alerts."""
    import uuid as uuid_mod

    keep_base = str(body.keep_api_url).rstrip("/")
    headers = _keep_headers(body.keep_api_key)
    rule_result: dict[str, Any] | None = None
    run_id = uuid_mod.uuid4().hex[:8]

    if body.create_rule:
        rule_result = await _ensure_correlation_rule(
            keep_base=keep_base,
            headers=headers,
            rule=GRAFANA_GPU_CORRELATION_RULE,
        )

    provider_id = body.provider_id or (_registry.get("grafana") or {}).get(
        "keep_provider_id"
    )
    scenario_ids: list[str] = (
        list(GRAFANA_GPU_SCENARIOS)
        if body.send_all_gpu
        else list(GRAFANA_GPU_DEMO_SCENARIO_IDS)
    )
    send_results = await _send_grafana_scenarios(
        keep_base=keep_base,
        headers=headers,
        provider_id=provider_id,
        scenario_ids=scenario_ids,
        status=body.status,
        run_id=run_id,
    )

    return {
        "ok": True,
        "run_id": run_id,
        "pack": "nvidia-gpu",
        "correlation_rule": rule_result,
        "events": send_results,
        "next_steps": (
            "Open Keep → Incidents. After alerts are processed, look for "
            f"'{GRAFANA_GPU_CORRELATION_RULE['incidentPrefix']}' / NVIDIA_GPU_* "
            "(threshold=2, group by labels.host, labels.code starts with NVIDIA_GPU)."
        ),
    }


@app.post("/api/register")
async def register_provider(body: RegisterRequest) -> dict[str, Any]:
    meta = PROVIDER_CATALOG[body.provider]
    public_base = str(body.public_base_url or PUBLIC_BASE_URL).rstrip("/")
    provider_name = body.provider_name or meta["default_name"]
    keep_type = meta["keep_type"]
    auth = _mock_auth_config(
        body.provider,
        public_base,
        temporal_address=body.temporal_address,
        temporal_namespace=body.temporal_namespace,
        temporal_tls=body.temporal_tls,
    )

    payload = {
        "provider_id": keep_type,
        "provider_name": provider_name,
        "provider_type": keep_type,
        "pulling_enabled": False,
        **auth,
    }

    url = urljoin(str(body.keep_api_url).rstrip("/") + "/", "providers/install")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                url,
                headers=_keep_headers(body.keep_api_key),
                json=payload,
            )
    except httpx.HTTPError as exc:
        _log(
            {
                "action": "register",
                "provider": body.provider,
                "ok": False,
                "error": str(exc),
            }
        )
        raise HTTPException(
            status_code=502,
            detail=f"Failed to reach Keep API at {url}: {exc}",
        ) from exc

    if resp.status_code >= 400:
        detail: Any
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text
        _log(
            {
                "action": "register",
                "provider": body.provider,
                "ok": False,
                "status_code": resp.status_code,
                "response": detail,
            }
        )
        raise HTTPException(status_code=resp.status_code, detail=detail)

    result = resp.json()
    registration = {
        "keep_provider_id": result.get("id"),
        "keep_type": keep_type,
        "provider_name": provider_name,
        "public_base_url": public_base,
        "auth": auth,
        "install_response": result,
        "keep_api_url": str(body.keep_api_url).rstrip("/"),
    }
    _registry[body.provider] = registration
    _log(
        {
            "action": "register",
            "provider": body.provider,
            "ok": True,
            "keep_provider_id": registration["keep_provider_id"],
        }
    )
    return {"ok": True, "registration": registration}


@app.delete("/api/register/{provider}")
async def unregister_provider(
    provider: ProviderKey,
    keep_api_url: str = DEFAULT_KEEP_API_URL,
    keep_api_key: str = DEFAULT_KEEP_API_KEY,
) -> dict[str, Any]:
    registration = _registry.get(provider)
    if not registration:
        raise HTTPException(status_code=404, detail="Provider not registered in mock")

    provider_id = registration["keep_provider_id"]
    keep_type = registration["keep_type"]
    url = urljoin(
        keep_api_url.rstrip("/") + "/",
        f"providers/{keep_type}/{provider_id}",
    )
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.delete(
                url, headers=_keep_headers(keep_api_key)
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502, detail=f"Failed to reach Keep API: {exc}"
        ) from exc

    if resp.status_code >= 400 and resp.status_code != 404:
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text
        raise HTTPException(status_code=resp.status_code, detail=detail)

    del _registry[provider]
    _log({"action": "unregister", "provider": provider, "ok": True})
    return {"ok": True}


@app.post("/api/send-event")
async def send_event(body: SendEventRequest) -> dict[str, Any]:
    meta = PROVIDER_CATALOG[body.provider]
    if not meta.get("supports_events", True):
        raise HTTPException(
            status_code=400,
            detail=(
                f"{meta['label']} does not support alert webhook events. "
                "Register it, then drive Temporal from a Keep workflow action."
            ),
        )
    keep_type = meta["keep_type"]
    if body.payload is not None:
        payload = body.payload
    elif body.provider == "grafana" and body.scenario:
        payload = build_grafana_scenario_payload(body.scenario, status=body.status)
    else:
        payload = build_payload(
            body.provider,
            status=body.status,
            alertname=body.alertname,
            severity=body.severity,
        )

    provider_id = body.provider_id
    if not provider_id and not body.use_linked:
        provider_id = (_registry.get(body.provider) or {}).get("keep_provider_id")

    path = f"alerts/event/{keep_type}"
    query = f"?provider_id={provider_id}" if provider_id else ""
    url = urljoin(str(body.keep_api_url).rstrip("/") + "/", path) + query

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                url,
                headers=_keep_headers(body.keep_api_key),
                json=payload,
            )
    except httpx.HTTPError as exc:
        _log(
            {
                "action": "send-event",
                "provider": body.provider,
                "ok": False,
                "error": str(exc),
                "url": url,
                "scenario": body.scenario,
            }
        )
        raise HTTPException(
            status_code=502,
            detail=f"Failed to reach Keep webhook at {url}: {exc}",
        ) from exc

    try:
        response_body: Any = resp.json()
    except Exception:
        response_body = resp.text

    ok = resp.status_code < 400
    _log(
        {
            "action": "send-event",
            "provider": body.provider,
            "ok": ok,
            "status_code": resp.status_code,
            "url": url,
            "provider_id": provider_id,
            "scenario": body.scenario,
            "payload_alertname": (
                (payload.get("alerts") or [{}])[0].get("labels", {}) or {}
            ).get("alertname"),
            "response": response_body,
        }
    )

    if not ok:
        raise HTTPException(status_code=resp.status_code, detail=response_body)

    return {
        "ok": True,
        "url": url,
        "provider_id": provider_id,
        "keep_type": keep_type,
        "status_code": resp.status_code,
        "response": response_body,
        "payload": payload,
        "scenario": body.scenario,
    }


@app.post("/api/preview-payload")
async def preview_payload(body: SendEventRequest) -> dict[str, Any]:
    meta = PROVIDER_CATALOG[body.provider]
    if not meta.get("supports_events", True):
        raise HTTPException(
            status_code=400,
            detail=f"{meta['label']} does not produce alert webhook payloads",
        )
    if body.payload is not None:
        payload = body.payload
    elif body.provider == "grafana" and body.scenario:
        payload = build_grafana_scenario_payload(body.scenario, status=body.status)
    else:
        payload = build_payload(
            body.provider,
            status=body.status,
            alertname=body.alertname,
            severity=body.severity,
        )
    return {
        "keep_type": meta["keep_type"],
        "payload": payload,
        "scenario": body.scenario,
    }


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
