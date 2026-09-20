"""NVIDIA AI datacenter inventory shared by mock alerts and Keep topology.

Hierarchy: region → datacenter → row → rack → host → GPU.
Alert labels use the same `service` names so the topology map can badge
the physical path of a firing GPU alert.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Iterable

import yaml

CLUSTER = "ai-dc-prod"
SERVICE = "gpu-inference"
VENDOR = "nvidia"
GPU_MODEL = "NVIDIA-H100-80GB-HBM3"
NAMESPACE = "ml-serving"
REGION = "us-west-2"
DATACENTER = "ai-dc-1"
DEFAULT_HOST = "gpu-node-a03"
DEFAULT_GPU_INDEX = 0
FABRIC_PREFIX = "10.12.0.0/24"
FABRIC_VLAN_VID = 100
FABRIC_VLAN_SLUG = "gpu-fabric"
APPLICATION_NAME = "NVIDIA GPU Inference"
APPLICATION_ID = "7c0a0a10-5e11-4b2a-9c3d-00a1dc000001"
APPLICATION_DESCRIPTION = (
    "Mock NVIDIA H100 inference cluster laid out by region / datacenter / "
    "row / rack / GPU for Keep Service Topology."
)
TEAM = "AI DC Ops"
SLACK = "#ai-dc-alerts"
EMAIL = "ops@ai-dc.local"

# (scenario_id, host, gpu_index). Demo pair (temp/mem) share the default host
# so Keep still correlates them into one GPU incident.
SCENARIO_LOCATIONS: dict[str, tuple[str, int]] = {
    "gpu_temp": (DEFAULT_HOST, 0),
    "gpu_mem": (DEFAULT_HOST, 0),
    "gpu_xid": (DEFAULT_HOST, 1),
    "gpu_ecc": ("gpu-node-a01", 0),
    "gpu_throttle": ("gpu-node-a01", 1),
    "gpu_nvlink": ("gpu-node-b01", 0),
    "gpu_power": ("gpu-node-b01", 1),
    "gpu_unavailable": (DEFAULT_HOST, 0),
}

HOSTS: tuple[dict[str, Any], ...] = (
    {
        "host": "gpu-node-a01",
        "region": REGION,
        "datacenter": DATACENTER,
        "row": "row-a",
        "rack": "rack-11",
        "ip": "10.12.0.11/24",
        "cluster": CLUSTER,
        "vendor": VENDOR,
        "gpu_model": GPU_MODEL,
        "namespace": NAMESPACE,
        "gpus": (
            {"index": 0, "uuid": "GPU-11111111-aaaa-4000-8000-000000000001"},
            {"index": 1, "uuid": "GPU-11111111-aaaa-4000-8000-000000000002"},
        ),
    },
    {
        "host": DEFAULT_HOST,
        "region": REGION,
        "datacenter": DATACENTER,
        "row": "row-a",
        "rack": "rack-12",
        "ip": "10.12.0.13/24",
        "cluster": CLUSTER,
        "vendor": VENDOR,
        "gpu_model": GPU_MODEL,
        "namespace": NAMESPACE,
        "gpus": (
            {"index": 0, "uuid": "GPU-a1b2c3d4-e5f6-7890"},
            {"index": 1, "uuid": "GPU-a1b2c3d4-e5f6-7891"},
        ),
    },
    {
        "host": "gpu-node-b01",
        "region": REGION,
        "datacenter": DATACENTER,
        "row": "row-b",
        "rack": "rack-21",
        "ip": "10.12.0.21/24",
        "cluster": CLUSTER,
        "vendor": VENDOR,
        "gpu_model": GPU_MODEL,
        "namespace": NAMESPACE,
        "gpus": (
            {"index": 0, "uuid": "GPU-22222222-bbbb-4000-8000-000000000001"},
            {"index": 1, "uuid": "GPU-22222222-bbbb-4000-8000-000000000002"},
        ),
    },
)


def gpu_service_name(host: str, gpu_index: int) -> str:
    return f"{host}-gpu{int(gpu_index)}"


def get_host(host: str) -> dict[str, Any]:
    for item in HOSTS:
        if item["host"] == host:
            return item
    raise KeyError(f"Unknown GPU host '{host}'")


def get_gpu(host: str, gpu_index: int) -> dict[str, Any]:
    node = get_host(host)
    for gpu in node["gpus"]:
        if int(gpu["index"]) == int(gpu_index):
            return {**gpu, "host": host}
    raise KeyError(f"Unknown GPU {gpu_index} on {host}")


def location_labels(host: str = DEFAULT_HOST, gpu_index: int = DEFAULT_GPU_INDEX) -> dict[str, str]:
    """Grafana / Alertmanager labels for one GPU in the inventory."""
    node = get_host(host)
    gpu = get_gpu(host, gpu_index)
    return {
        "service": SERVICE,
        "host": node["host"],
        "cluster": node["cluster"],
        "region": node["region"],
        "datacenter": node["datacenter"],
        "row": node["row"],
        "rack": node["rack"],
        "gpu": str(gpu["index"]),
        "gpu_id": gpu_service_name(host, gpu["index"]),
        "gpu_uuid": gpu["uuid"],
        "gpu_model": node["gpu_model"],
        "namespace": node["namespace"],
        "vendor": node["vendor"],
    }


def location_for_scenario(scenario_id: str) -> dict[str, str]:
    host, gpu_index = SCENARIO_LOCATIONS.get(
        scenario_id, (DEFAULT_HOST, DEFAULT_GPU_INDEX)
    )
    return location_labels(host, gpu_index)


def default_server_snapshot() -> dict[str, Any]:
    """In-memory mock node used by Temporal remediations (default host)."""
    node = get_host(DEFAULT_HOST)
    return {
        "host": node["host"],
        "region": node["region"],
        "datacenter": node["datacenter"],
        "row": node["row"],
        "rack": node["rack"],
        "cluster": node["cluster"],
        "vendor": node["vendor"],
        "gpu_model": node["gpu_model"],
        "namespace": node["namespace"],
        "gpus": [
            {
                "index": gpu["index"],
                "uuid": gpu["uuid"],
                "health": "ok",
                "temperature_c": 62.0,
                "memory_util_pct": 41.0,
                "xid": None,
            }
            for gpu in node["gpus"]
        ],
    }


def inventory_nodes() -> list[dict[str, Any]]:
    """All hosts with live-style GPU slots (used by GET /gpu/topology)."""
    nodes = []
    for host in HOSTS:
        nodes.append(
            {
                **{k: host[k] for k in host if k != "gpus"},
                "gpus": [
                    {
                        "index": gpu["index"],
                        "uuid": gpu["uuid"],
                        "gpu_id": gpu_service_name(host["host"], gpu["index"]),
                        "health": "ok",
                    }
                    for gpu in host["gpus"]
                ],
            }
        )
    return nodes


def _node(
    *,
    service: str,
    display_name: str,
    category: str,
    description: str,
    tags: list[str],
    namespace: str | None = NAMESPACE,
    manufacturer: str | None = "NVIDIA",
) -> dict[str, Any]:
    return {
        "service": service,
        "display_name": display_name,
        "environment": "prod",
        "description": description,
        "team": TEAM,
        "email": EMAIL,
        "slack": SLACK,
        "category": category,
        "manufacturer": manufacturer,
        "namespace": namespace,
        "is_manual": True,
        "tags": tags,
        "source_provider_id": "nvidia-gpu-mock",
    }


def iter_topology_services() -> list[dict[str, Any]]:
    services: list[dict[str, Any]] = [
        _node(
            service=REGION,
            display_name=f"Region {REGION}",
            category="region",
            description="AWS-style region that hosts the AI datacenter.",
            tags=["nvidia", "region"],
            namespace=None,
            manufacturer=None,
        ),
        _node(
            service=DATACENTER,
            display_name=f"Datacenter {DATACENTER}",
            category="datacenter",
            description="AI datacenter floor for NVIDIA H100 inference.",
            tags=["nvidia", "datacenter"],
            namespace=None,
        ),
    ]
    rows = sorted({host["row"] for host in HOSTS})
    racks = sorted({(host["row"], host["rack"]) for host in HOSTS})
    for row in rows:
        services.append(
            _node(
                service=row,
                display_name=f"Row {row.split('-', 1)[-1].upper()}",
                category="row",
                description=f"Hot/cold aisle {row} in {DATACENTER}.",
                tags=["nvidia", "row"],
                namespace=None,
            )
        )
    for row, rack in racks:
        services.append(
            _node(
                service=rack,
                display_name=f"Rack {rack.split('-', 1)[-1]}",
                category="rack",
                description=f"GPU rack {rack} in {row}.",
                tags=["nvidia", "rack"],
                namespace=None,
            )
        )
    for host in HOSTS:
        services.append(
            _node(
                service=host["host"],
                display_name=host["host"],
                category="host",
                description=(
                    f"NVIDIA H100 node in {host['datacenter']} / {host['row']} / "
                    f"{host['rack']}."
                ),
                tags=["nvidia", "host", host["rack"], host["row"]],
            )
        )
        for gpu in host["gpus"]:
            gpu_id = gpu_service_name(host["host"], gpu["index"])
            services.append(
                _node(
                    service=gpu_id,
                    display_name=f"GPU {gpu['index']} @ {host['host']}",
                    category="gpu",
                    description=(
                        f"{host['gpu_model']} index {gpu['index']} "
                        f"({gpu['uuid']}) in {host['rack']}."
                    ),
                    tags=["nvidia", "gpu", host["host"], host["rack"]],
                )
            )
    services.append(
        _node(
            service=SERVICE,
            display_name="GPU Inference",
            category="service",
            description="Logical inference service that consumes the H100 fleet.",
            tags=["nvidia", "inference"],
        )
    )
    return services


def iter_topology_dependencies() -> list[dict[str, str]]:
    """Child → parent containment (A depends on B)."""
    deps: list[dict[str, str]] = [
        {
            "source": DATACENTER,
            "target": REGION,
            "protocol": "located-in",
        },
    ]
    rows = sorted({host["row"] for host in HOSTS})
    racks = sorted({(host["row"], host["rack"]) for host in HOSTS})
    for row in rows:
        deps.append({"source": row, "target": DATACENTER, "protocol": "located-in"})
    for row, rack in racks:
        deps.append({"source": rack, "target": row, "protocol": "located-in"})
    for host in HOSTS:
        deps.append(
            {"source": host["host"], "target": host["rack"], "protocol": "power"}
        )
        for gpu in host["gpus"]:
            gpu_id = gpu_service_name(host["host"], gpu["index"])
            deps.append({"source": gpu_id, "target": host["host"], "protocol": "PCIe"})
            deps.append({"source": SERVICE, "target": gpu_id, "protocol": "CUDA"})
    return deps


def build_keep_topology_spec() -> dict[str, Any]:
    """REST-friendly spec (service names, not numeric IDs)."""
    services = iter_topology_services()
    return {
        "application": {
            "id": APPLICATION_ID,
            "name": APPLICATION_NAME,
            "description": APPLICATION_DESCRIPTION,
            "repository": "",
            "services": [item["service"] for item in services],
        },
        "services": services,
        "dependencies": iter_topology_dependencies(),
    }


def build_keep_topology_yaml_dict() -> dict[str, Any]:
    """YAML import shape used by POST /topology/import."""
    services = iter_topology_services()
    name_to_id = {item["service"]: idx + 1 for idx, item in enumerate(services)}
    yaml_services = []
    for item in services:
        yaml_services.append({"id": name_to_id[item["service"]], **item})
    yaml_deps = []
    for dep in iter_topology_dependencies():
        yaml_deps.append(
            {
                "service_id": name_to_id[dep["source"]],
                "depends_on_service_id": name_to_id[dep["target"]],
                "protocol": dep["protocol"],
            }
        )
    return {
        "applications": [
            {
                "id": APPLICATION_ID,
                "name": APPLICATION_NAME,
                "description": APPLICATION_DESCRIPTION,
                "repository": "",
                "services": [item["id"] for item in yaml_services],
            }
        ],
        "dependencies": yaml_deps,
        "services": yaml_services,
    }


def topology_yaml_text(data: dict[str, Any] | None = None) -> str:
    """Keep-compatible YAML for export / import."""
    payload = data if data is not None else build_keep_topology_yaml_dict()
    return yaml.safe_dump(
        payload,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=120,
    )


def parse_topology_document(text: str) -> dict[str, Any]:
    """Parse Keep topology YAML or JSON. Raises ValueError on invalid docs."""
    raw = (text or "").strip()
    if not raw:
        raise ValueError("Empty topology document")
    try:
        if raw[0] in "{[":
            data = json.loads(raw)
        else:
            data = yaml.safe_load(raw)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ValueError(f"Invalid topology YAML/JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Topology document must be a mapping")
    services = data.get("services")
    if not isinstance(services, list) or not services:
        raise ValueError("Topology document must include a non-empty services list")
    data.setdefault("applications", [])
    data.setdefault("dependencies", [])
    if data["applications"] is None:
        data["applications"] = []
    if data["dependencies"] is None:
        data["dependencies"] = []
    return data


RequestFn = Callable[..., tuple[int, Any]]


def _json_list(payload: Any) -> list:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("applications", "items", "data", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def _application_body(spec: dict[str, Any], by_name: dict[str, dict]) -> dict[str, Any]:
    service_ids = []
    for name in spec["application"]["services"]:
        item = by_name.get(name)
        sid = _as_int(item.get("id")) if item else None
        if sid is not None:
            service_ids.append({"id": sid})
    return {
        "id": spec["application"]["id"],
        "name": spec["application"]["name"],
        "description": spec["application"]["description"],
        "repository": spec["application"].get("repository") or "",
        "services": service_ids,
    }


def apply_keep_topology(request_fn: RequestFn) -> dict[str, Any]:
    """Idempotently create NVIDIA topology via Keep REST.

    `request_fn(method, path, body=None) -> (status, json)`.
    """
    spec = build_keep_topology_spec()
    status, existing = request_fn("GET", "/topology?include_empty_deps=true")
    if status >= 400:
        raise RuntimeError(f"GET /topology failed ({status}): {existing}")
    by_name = {
        item.get("service"): item
        for item in _json_list(existing)
        if isinstance(item, dict) and item.get("service")
    }

    created_services: list[str] = []
    for svc in spec["services"]:
        name = svc["service"]
        if name in by_name:
            continue
        body = {
            key: value
            for key, value in svc.items()
            if key not in {"source_provider_id"}
        }
        code, created = request_fn("POST", "/topology/service", body)
        if code not in (200, 201) or not isinstance(created, dict):
            raise RuntimeError(f"POST /topology/service {name} failed ({code}): {created}")
        by_name[name] = created
        created_services.append(name)

    status, existing = request_fn("GET", "/topology?include_empty_deps=true")
    if status >= 400:
        raise RuntimeError(f"GET /topology refresh failed ({status}): {existing}")
    by_name = {
        item.get("service"): item
        for item in _json_list(existing)
        if isinstance(item, dict) and item.get("service")
    }

    existing_deps: set[tuple[int, int]] = set()
    for item in _json_list(existing):
        if not isinstance(item, dict):
            continue
        src_id = _as_int(item.get("id"))
        if src_id is None:
            continue
        for dep in item.get("dependencies") or []:
            if not isinstance(dep, dict):
                continue
            dst_id = _as_int(dep.get("serviceId") or dep.get("depends_on_service_id"))
            if dst_id is not None:
                existing_deps.add((src_id, dst_id))

    created_deps = 0
    for dep in spec["dependencies"]:
        src = by_name.get(dep["source"])
        dst = by_name.get(dep["target"])
        if not src or not dst:
            continue
        src_id = _as_int(src.get("id"))
        dst_id = _as_int(dst.get("id"))
        if src_id is None or dst_id is None or (src_id, dst_id) in existing_deps:
            continue
        code, _ = request_fn(
            "POST",
            "/topology/dependency",
            {
                "service_id": src_id,
                "depends_on_service_id": dst_id,
                "protocol": dep["protocol"],
            },
        )
        if code not in (200, 201):
            raise RuntimeError(
                f"POST /topology/dependency {dep['source']}→{dep['target']} "
                f"failed ({code})"
            )
        existing_deps.add((src_id, dst_id))
        created_deps += 1

    status, apps = request_fn("GET", "/topology/applications")
    if status >= 400:
        raise RuntimeError(f"GET /topology/applications failed ({status}): {apps}")
    app_name = spec["application"]["name"]
    app_id = str(spec["application"]["id"])
    matches = [
        app
        for app in _json_list(apps)
        if isinstance(app, dict)
        and (app.get("name") == app_name or str(app.get("id") or "") == app_id)
    ]
    created_app = False
    body = _application_body(spec, by_name)
    if not body["services"]:
        return {
            "ok": True,
            "application": app_name,
            "services_total": len(spec["services"]),
            "services_created": created_services,
            "dependencies_created": created_deps,
            "application_created": False,
        }

    keeper = next(
        (app for app in matches if str(app.get("id") or "") == app_id),
        matches[0] if matches else None,
    )
    for extra in matches:
        extra_id = extra.get("id")
        if keeper is None or extra_id is None or str(extra_id) == str(keeper.get("id")):
            continue
        code, _ = request_fn("DELETE", f"/topology/applications/{extra_id}")
        if code not in (200, 204) and code >= 400:
            raise RuntimeError(
                f"DELETE /topology/applications/{extra_id} failed ({code})"
            )

    if keeper and keeper.get("id"):
        put_body = {**body, "id": keeper["id"]}
        code, _ = request_fn(
            "PUT", f"/topology/applications/{keeper['id']}", put_body
        )
        if code not in (200, 201):
            raise RuntimeError(
                f"PUT /topology/applications/{keeper['id']} failed ({code})"
            )
    else:
        code, _ = request_fn("POST", "/topology/applications", body)
        if code not in (200, 201):
            raise RuntimeError(f"POST /topology/applications failed ({code})")
        created_app = True

    return {
        "ok": True,
        "application": app_name,
        "services_total": len(spec["services"]),
        "services_created": created_services,
        "dependencies_created": created_deps,
        "application_created": created_app,
    }


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def topology_summary() -> dict[str, Any]:
    spec = build_keep_topology_spec()
    return {
        "cluster": CLUSTER,
        "region": REGION,
        "datacenter": DATACENTER,
        "application": APPLICATION_NAME,
        "hosts": [host["host"] for host in HOSTS],
        "rows": sorted({host["row"] for host in HOSTS}),
        "racks": sorted({host["rack"] for host in HOSTS}),
        "gpu_ids": [
            gpu_service_name(host["host"], gpu["index"])
            for host in HOSTS
            for gpu in host["gpus"]
        ],
        "default_host": DEFAULT_HOST,
        "services": [item["service"] for item in spec["services"]],
        "dependencies": spec["dependencies"],
    }


def iter_hosts() -> Iterable[dict[str, Any]]:
    return HOSTS
