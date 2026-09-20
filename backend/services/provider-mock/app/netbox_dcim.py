"""Seed NetBox DCIM with the NVIDIA GPU inventory used by provider-mock topology."""

from __future__ import annotations

from typing import Any, Callable, Optional
from urllib.parse import urljoin

import httpx

from app.gpu_topology import (
    DATACENTER,
    FABRIC_PREFIX,
    FABRIC_VLAN_SLUG,
    FABRIC_VLAN_VID,
    HOSTS,
    REGION,
    gpu_service_name,
)

RequestFn = Callable[[str, str, dict[str, str], Optional[dict], Optional[dict]], tuple[int, Any]]

NETBOX_PROVIDER_NAME = "netbox-nvidia-gpu"
DEFAULT_TOKEN = "0123456789abcdef0123456789abcdef01234567"


class NetBoxError(RuntimeError):
    def __init__(self, status: int, detail: Any):
        self.status = status
        self.detail = detail
        super().__init__(f"NetBox HTTP {status}: {detail}")


def build_dcim_plan() -> dict[str, Any]:
    """Same region/row/rack/GPU graph as mock Service Topology, plus fabric IPAM."""
    rows = sorted({host["row"] for host in HOSTS})
    racks = sorted({(host["row"], host["rack"]) for host in HOSTS})
    return {
        "region": {"name": REGION, "slug": REGION},
        "site": {
            "name": DATACENTER,
            "slug": DATACENTER,
            "status": "active",
            "region": REGION,
        },
        "rows": [{"name": row, "slug": row, "status": "active"} for row in rows],
        "racks": [
            {"name": rack, "row": row, "status": "active", "u_height": 42}
            for row, rack in racks
        ],
        "hosts": [
            {
                "name": host["host"],
                "row": host["row"],
                "rack": host["rack"],
                "ip": host.get("ip"),
                "gpus": [
                    {
                        "index": gpu["index"],
                        "name": f"GPU {gpu['index']}",
                        "uuid": gpu["uuid"],
                        "gpu_id": gpu_service_name(host["host"], gpu["index"]),
                        "part_id": "H100",
                    }
                    for gpu in host["gpus"]
                ],
            }
            for host in HOSTS
        ],
        "vlan": {
            "vid": FABRIC_VLAN_VID,
            "name": FABRIC_VLAN_SLUG,
            "slug": FABRIC_VLAN_SLUG,
            "status": "active",
        },
        "prefix": {
            "prefix": FABRIC_PREFIX,
            "status": "active",
            "description": "GPU fabric",
        },
        "manufacturer": {"name": "NVIDIA", "slug": "nvidia"},
        "device_role": {
            "name": "GPU Server",
            "slug": "gpu-server",
            "color": "76b900",
        },
        "device_type": {
            "model": "DGX H100",
            "slug": "dgx-h100",
            "u_height": 2,
        },
        "inventory_role": {"name": "GPU", "slug": "gpu", "color": "76b900"},
    }


class NetBoxClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        verify: bool = False,
        timeout: float = 45.0,
        request_fn: RequestFn | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.verify = verify
        self.timeout = timeout
        self._request_fn = request_fn

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Token {self.token}",
        }

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> tuple[int, Any]:
        url = path if path.startswith("http") else urljoin(self.base_url + "/", path.lstrip("/"))
        if self._request_fn:
            return self._request_fn(method, url, self.headers, json_body, params)
        try:
            with httpx.Client(timeout=self.timeout, verify=self.verify) as client:
                resp = client.request(
                    method, url, headers=self.headers, json=json_body, params=params
                )
        except httpx.HTTPError as exc:
            raise NetBoxError(502, str(exc)) from exc
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        return resp.status_code, body

    def status(self) -> dict[str, Any]:
        code, body = self.request("GET", "/api/status/")
        return {
            "ok": code < 400,
            "status_code": code,
            "body": body,
            "url": self.base_url,
        }

    def list(self, path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        code, body = self.request("GET", path, params=params)
        if code >= 400:
            raise NetBoxError(code, body)
        if isinstance(body, dict) and isinstance(body.get("results"), list):
            return body["results"]
        if isinstance(body, list):
            return body
        return []

    def ensure(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        query: dict[str, Any],
    ) -> dict[str, Any]:
        existing = self.list(path, query)
        if existing:
            return existing[0]
        code, body = self.request("POST", path, json_body=payload)
        if code in {200, 201} and isinstance(body, dict) and body.get("id") is not None:
            return body
        existing = self.list(path, query)
        if existing:
            return existing[0]
        raise NetBoxError(code, body)


def seed_nvidia_dcim(client: NetBoxClient) -> dict[str, Any]:
    """Idempotently create the NVIDIA GPU DCIM/IPAM objects in NetBox."""
    plan = build_dcim_plan()
    created: dict[str, Any] = {"plan": plan, "ids": {}}

    manufacturer = client.ensure(
        "/api/dcim/manufacturers/",
        plan["manufacturer"],
        query={"slug": plan["manufacturer"]["slug"]},
    )
    role = client.ensure(
        "/api/dcim/device-roles/",
        plan["device_role"],
        query={"slug": plan["device_role"]["slug"]},
    )
    device_type = client.ensure(
        "/api/dcim/device-types/",
        {**plan["device_type"], "manufacturer": manufacturer["id"]},
        query={"slug": plan["device_type"]["slug"]},
    )
    try:
        gpu_role = client.ensure(
            "/api/dcim/inventory-item-roles/",
            plan["inventory_role"],
            query={"slug": plan["inventory_role"]["slug"]},
        )
    except NetBoxError as exc:
        if exc.status not in {403, 404}:
            raise
        gpu_role = None

    region = client.ensure(
        "/api/dcim/regions/",
        plan["region"],
        query={"slug": plan["region"]["slug"]},
    )
    site = client.ensure(
        "/api/dcim/sites/",
        {
            "name": plan["site"]["name"],
            "slug": plan["site"]["slug"],
            "status": plan["site"]["status"],
            "region": region["id"],
        },
        query={"slug": plan["site"]["slug"]},
    )
    locations: dict[str, dict[str, Any]] = {}
    for row in plan["rows"]:
        locations[row["slug"]] = client.ensure(
            "/api/dcim/locations/",
            {**row, "site": site["id"]},
            query={"slug": row["slug"], "site_id": site["id"]},
        )
    racks: dict[str, dict[str, Any]] = {}
    for rack in plan["racks"]:
        racks[rack["name"]] = client.ensure(
            "/api/dcim/racks/",
            {
                "name": rack["name"],
                "site": site["id"],
                "location": locations[rack["row"]]["id"],
                "status": rack["status"],
                "u_height": rack["u_height"],
            },
            query={"name": rack["name"], "site_id": site["id"]},
        )
    vlan = client.ensure(
        "/api/ipam/vlans/",
        {**plan["vlan"], "site": site["id"]},
        query={"vid": plan["vlan"]["vid"], "site_id": site["id"]},
    )
    prefix = client.ensure(
        "/api/ipam/prefixes/",
        {
            **plan["prefix"],
            "site": site["id"],
            "vlan": vlan["id"],
        },
        query={"prefix": plan["prefix"]["prefix"]},
    )

    devices: dict[str, dict[str, Any]] = {}
    gpus: list[dict[str, Any]] = []
    for host in plan["hosts"]:
        device = client.ensure(
            "/api/dcim/devices/",
            {
                "name": host["name"],
                "device_type": device_type["id"],
                "role": role["id"],
                "site": site["id"],
                "location": locations[host["row"]]["id"],
                "rack": racks[host["rack"]]["id"],
                "status": "active",
                "face": "front",
                "position": 1,
            },
            query={"name": host["name"], "site_id": site["id"]},
        )
        devices[host["name"]] = device
        iface = client.ensure(
            "/api/dcim/interfaces/",
            {
                "device": device["id"],
                "name": "eth0",
                "type": "25gbase-x-sfp28",
            },
            query={"device_id": device["id"], "name": "eth0"},
        )
        if host.get("ip"):
            ip = client.ensure(
                "/api/ipam/ip-addresses/",
                {
                    "address": host["ip"],
                    "status": "active",
                    "assigned_object_type": "dcim.interface",
                    "assigned_object_id": iface["id"],
                },
                query={"address": host["ip"]},
            )
            if not device.get("primary_ip4"):
                client.request(
                    "PATCH",
                    f"/api/dcim/devices/{device['id']}/",
                    json_body={"primary_ip4": ip["id"]},
                )
        for gpu in host["gpus"]:
            payload = {
                "device": device["id"],
                "name": gpu["name"],
                "label": gpu["uuid"],
                "part_id": gpu["part_id"],
                "manufacturer": manufacturer["id"],
            }
            if gpu_role:
                payload["role"] = gpu_role["id"]
            item = client.ensure(
                "/api/dcim/inventory-items/",
                payload,
                query={"device_id": device["id"], "name": gpu["name"]},
            )
            gpus.append({"host": host["name"], "gpu_id": gpu["gpu_id"], "id": item["id"]})

    created["ids"] = {
        "region": region["id"],
        "site": site["id"],
        "locations": {slug: obj["id"] for slug, obj in locations.items()},
        "racks": {name: obj["id"] for name, obj in racks.items()},
        "devices": {name: obj["id"] for name, obj in devices.items()},
        "vlan": vlan["id"],
        "prefix": prefix["id"],
        "gpus": gpus,
    }
    created["counts"] = {
        "rows": len(locations),
        "racks": len(racks),
        "hosts": len(devices),
        "gpus": len(gpus),
    }
    return created


def find_installed_netbox(
    installed: list[dict[str, Any]],
    *,
    provider_name: str = NETBOX_PROVIDER_NAME,
) -> dict[str, Any] | None:
    """Match Keep's installed NetBox provider by instance name, not UUID `id`."""
    matches = [
        item
        for item in installed
        if (item.get("type") or item.get("provider_type")) == "netbox"
    ]
    for item in matches:
        details = item.get("details") if isinstance(item.get("details"), dict) else {}
        name = details.get("name") or item.get("name")
        if name == provider_name:
            return item
    return matches[0] if matches else None
