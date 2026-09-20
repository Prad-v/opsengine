"""NetBox provider webhook formatting and DCIM topology sync."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse

import requests

from keep.api.models.db.topology import TopologyServiceInDto
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseTopologyProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.netbox_provider.alerts_mock import ALERTS
from keep.providers.netbox_provider.netbox_provider import NetboxProvider
from keep.providers.netbox_provider.topology import (
    DEFAULT_GPU_PATTERN,
    NetboxInventory,
    address_in_prefix,
    build_topology_services,
    gpu_service_name,
    is_gpu_component,
)
from keep.providers.providers_factory import ProvidersFactory


def _nested(slug: str, name: str | None = None) -> dict:
    return {"id": 1, "slug": slug, "name": name or slug, "display": name or slug}


def nvidia_style_inventory() -> NetboxInventory:
    """DCIM snapshot aligned with the NVIDIA GPU datacenter demo."""
    return NetboxInventory(
        regions=[
            {
                "id": 1,
                "slug": "us-west-2",
                "name": "us-west-2",
                "display": "us-west-2",
                "description": "AWS-style region",
            }
        ],
        sites=[
            {
                "id": 1,
                "slug": "ai-dc-1",
                "name": "ai-dc-1",
                "display": "ai-dc-1",
                "region": _nested("us-west-2"),
                "description": "AI datacenter",
            }
        ],
        locations=[
            {
                "id": 1,
                "slug": "row-a",
                "name": "row-a",
                "display": "Row A",
                "site": _nested("ai-dc-1"),
            },
            {
                "id": 2,
                "slug": "row-b",
                "name": "row-b",
                "display": "Row B",
                "site": _nested("ai-dc-1"),
            },
        ],
        racks=[
            {
                "id": 1,
                "name": "rack-11",
                "display": "rack-11",
                "site": _nested("ai-dc-1"),
                "location": _nested("row-a"),
            },
            {
                "id": 2,
                "name": "rack-12",
                "display": "rack-12",
                "site": _nested("ai-dc-1"),
                "location": _nested("row-a"),
            },
            {
                "id": 3,
                "name": "rack-21",
                "display": "rack-21",
                "site": _nested("ai-dc-1"),
                "location": _nested("row-b"),
            },
        ],
        devices=[
            {
                "id": 1,
                "name": "gpu-node-a01",
                "display": "gpu-node-a01",
                "site": _nested("ai-dc-1"),
                "rack": {"id": 1, "name": "rack-11", "display": "rack-11"},
                "primary_ip4": {"address": "10.12.0.11/24"},
                "device_type": {"manufacturer": {"name": "NVIDIA", "slug": "nvidia"}},
            },
            {
                "id": 2,
                "name": "gpu-node-a03",
                "display": "gpu-node-a03",
                "site": _nested("ai-dc-1"),
                "rack": {"id": 2, "name": "rack-12", "display": "rack-12"},
                "primary_ip4": {"address": "10.12.0.13/24"},
                "device_type": {"manufacturer": {"name": "NVIDIA", "slug": "nvidia"}},
            },
            {
                "id": 3,
                "name": "gpu-node-b01",
                "display": "gpu-node-b01",
                "site": _nested("ai-dc-1"),
                "rack": {"id": 3, "name": "rack-21", "display": "rack-21"},
                "primary_ip4": {"address": "10.12.0.21/24"},
                "device_type": {"manufacturer": {"name": "NVIDIA", "slug": "nvidia"}},
            },
        ],
        inventory_items=[
            {
                "id": 1,
                "name": "GPU 0",
                "device": {"name": "gpu-node-a03"},
                "role": {"slug": "gpu", "name": "GPU"},
                "manufacturer": {"name": "NVIDIA"},
                "part_id": "H100",
            },
            {
                "id": 2,
                "name": "GPU 1",
                "device": {"name": "gpu-node-a03"},
                "role": {"slug": "gpu", "name": "GPU"},
                "manufacturer": {"name": "NVIDIA"},
                "part_id": "H100",
            },
            {
                "id": 3,
                "name": "GPU 0",
                "device": {"name": "gpu-node-a01"},
                "role": {"slug": "gpu"},
                "part_id": "H100",
            },
            {
                "id": 4,
                "name": "GPU 1",
                "device": {"name": "gpu-node-a01"},
                "role": {"slug": "gpu"},
                "part_id": "H100",
            },
            {
                "id": 5,
                "name": "GPU 0",
                "device": {"name": "gpu-node-b01"},
                "role": {"slug": "gpu"},
                "part_id": "H100",
            },
            {
                "id": 6,
                "name": "GPU 1",
                "device": {"name": "gpu-node-b01"},
                "role": {"slug": "gpu"},
                "part_id": "H100",
            },
            {
                "id": 99,
                "name": "PSU 0",
                "device": {"name": "gpu-node-a03"},
                "role": {"slug": "psu"},
            },
        ],
        prefixes=[
            {
                "id": 1,
                "prefix": "10.12.0.0/24",
                "description": "GPU fabric",
                "site": _nested("ai-dc-1"),
                "vlan": {"vid": 100, "slug": "gpu-fabric", "name": "gpu-fabric"},
            }
        ],
        vlans=[
            {
                "id": 1,
                "vid": 100,
                "slug": "gpu-fabric",
                "name": "gpu-fabric",
                "display": "gpu-fabric",
                "site": _nested("ai-dc-1"),
            }
        ],
    )


def _by_service(nodes: list[TopologyServiceInDto]) -> dict[str, TopologyServiceInDto]:
    return {node.service: node for node in nodes}


def test_netbox_is_topology_provider():
    provider_class = ProvidersFactory.get_provider_class("netbox")
    assert issubclass(provider_class, BaseTopologyProvider)
    assert provider_class.PROVIDER_DISPLAY_NAME == "NetBox"


def test_format_alert_from_webhook_payload():
    alert = NetboxProvider._format_alert(ALERTS)
    assert alert.source == ["netbox"]
    assert alert.name == "Test"
    assert alert.description == "created"
    assert alert.model == "site"
    assert alert.username == "admin"
    assert alert.id == "7886b12c-593d-46bb-a781-5da0e5be255b"


def test_build_topology_maps_dcim_hierarchy():
    nodes = _by_service(build_topology_services("netbox-1", nvidia_style_inventory()))

    assert nodes["us-west-2"].category == "region"
    assert nodes["ai-dc-1"].category == "datacenter"
    assert nodes["ai-dc-1"].dependencies["us-west-2"] == "located-in"
    assert nodes["row-a"].category == "row"
    assert nodes["row-a"].dependencies["ai-dc-1"] == "located-in"
    assert nodes["rack-12"].category == "rack"
    assert nodes["rack-12"].dependencies["row-a"] == "located-in"
    assert nodes["gpu-node-a03"].category == "host"
    assert nodes["gpu-node-a03"].dependencies["rack-12"] == "power"
    assert nodes["gpu-node-a03"].ip_address == "10.12.0.13"
    assert nodes["gpu-node-a03"].manufacturer == "NVIDIA"

    gpu0 = nodes["gpu-node-a03-gpu0"]
    assert gpu0.category == "gpu"
    assert gpu0.dependencies["gpu-node-a03"] == "PCIe"
    assert "gpu-node-a03-gpu1" in nodes
    assert "PSU 0" not in nodes
    assert gpu_service_name("gpu-node-a03", 0) == "gpu-node-a03-gpu0"


def test_build_topology_maps_networks_and_l3():
    nodes = _by_service(build_topology_services("netbox-1", nvidia_style_inventory()))
    prefix = nodes["10.12.0.0/24"]
    assert prefix.category == "network"
    assert prefix.dependencies["ai-dc-1"] == "located-in"
    assert prefix.dependencies["vlan-100"] == "L2"
    assert nodes["vlan-100"].category == "network"
    assert nodes["gpu-node-a03"].dependencies["10.12.0.0/24"] == "L3"
    assert nodes["gpu-node-b01"].dependencies["10.12.0.0/24"] == "L3"


def test_build_topology_groups_site_application():
    nodes = build_topology_services("netbox-1", nvidia_style_inventory())
    site = next(node for node in nodes if node.service == "ai-dc-1")
    assert site.application_relations
    app_name = next(iter(site.application_relations.values()))
    assert app_name == "NetBox ai-dc-1"
    gpu = next(node for node in nodes if node.service == "gpu-node-a03-gpu0")
    assert gpu.application_relations == site.application_relations


def test_nested_location_depends_on_parent():
    inventory = NetboxInventory(
        sites=[{"slug": "ai-dc-1", "name": "ai-dc-1"}],
        locations=[
            {"slug": "building-1", "name": "building-1", "site": _nested("ai-dc-1")},
            {
                "slug": "row-a",
                "name": "row-a",
                "site": _nested("ai-dc-1"),
                "parent": _nested("building-1"),
            },
        ],
    )
    nodes = _by_service(build_topology_services("netbox-1", inventory))
    assert nodes["building-1"].dependencies["ai-dc-1"] == "located-in"
    assert nodes["row-a"].dependencies["building-1"] == "located-in"


def test_gpu_count_custom_field_when_no_inventory():
    inventory = NetboxInventory(
        sites=[{"slug": "ai-dc-1", "name": "ai-dc-1"}],
        devices=[
            {
                "name": "gpu-node-a03",
                "site": _nested("ai-dc-1"),
                "custom_fields": {"gpu_count": 2},
            }
        ],
    )
    nodes = _by_service(build_topology_services("netbox-1", inventory))
    assert "gpu-node-a03-gpu0" in nodes
    assert "gpu-node-a03-gpu1" in nodes
    assert nodes["gpu-node-a03-gpu1"].dependencies["gpu-node-a03"] == "PCIe"


def test_gpu_modules_preferred_over_inventory_items():
    inventory = NetboxInventory(
        devices=[{"name": "gpu-node-a03", "display": "gpu-node-a03"}],
        inventory_items=[
            {
                "name": "GPU 0",
                "device": {"name": "gpu-node-a03"},
                "role": {"slug": "gpu"},
            }
        ],
        modules=[
            {
                "name": "H100",
                "device": {"name": "gpu-node-a03"},
                "module_bay": {"name": "GPU1"},
                "module_type": {
                    "model": "H100 80GB",
                    "manufacturer": {"name": "NVIDIA"},
                },
            }
        ],
    )
    nodes = _by_service(build_topology_services("netbox-1", inventory))
    assert "gpu-node-a03-gpu1" in nodes
    assert "gpu-node-a03-gpu0" not in nodes
    assert "gpu-node-a03-gpu100" not in nodes


def test_is_gpu_component_and_address_helpers():
    import re

    pattern = re.compile(DEFAULT_GPU_PATTERN, re.I)
    assert is_gpu_component({"name": "NVIDIA H100 SXM"}, pattern)
    assert not is_gpu_component({"name": "PSU 0", "role": {"slug": "psu"}}, pattern)
    assert address_in_prefix("10.12.0.13/24", "10.12.0.0/24")
    assert not address_in_prefix("10.99.0.1/24", "10.12.0.0/24")
    assert not address_in_prefix("not-an-ip", "10.12.0.0/24")


def _provider(auth: dict | None = None) -> NetboxProvider:
    context_manager = MagicMock(spec=ContextManager)
    context_manager.tenant_id = "test-tenant"
    config = ProviderConfig(
        description="NetBox",
        authentication=auth if auth is not None else {},
    )
    return NetboxProvider(
        context_manager=context_manager,
        provider_id="netbox-test",
        config=config,
    )


def test_pull_topology_skips_without_credentials():
    services, apps = _provider().pull_topology()
    assert services == []
    assert apps == {}


def test_validate_scopes_without_credentials():
    scopes = _provider().validate_scopes()
    assert "dcim_read" in scopes
    assert scopes["dcim_read"] is not True


def _page(results, next_url=None):
    return {
        "count": len(results),
        "next": next_url,
        "previous": None,
        "results": results,
    }


def test_pull_topology_from_netbox_api():
    inventory = nvidia_style_inventory()
    pages = {
        "/api/dcim/regions/": _page(inventory.regions),
        "/api/dcim/sites/": _page(inventory.sites),
        "/api/dcim/locations/": _page(inventory.locations),
        "/api/dcim/racks/": _page(inventory.racks),
        "/api/dcim/devices/": _page(inventory.devices),
        "/api/dcim/inventory-items/": _page(inventory.inventory_items),
        "/api/dcim/modules/": _page([]),
        "/api/ipam/prefixes/": _page(inventory.prefixes),
        "/api/ipam/vlans/": _page(inventory.vlans),
    }

    def fake_get(url, **kwargs):
        path = urlparse(url).path
        if path not in pages:
            response = MagicMock()
            response.status_code = 404
            error = requests.HTTPError("not found")
            error.response = response
            raise error
        payload = pages[path]
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = payload
        resp.raise_for_status = MagicMock()
        return resp

    provider = _provider(
        {"netbox_url": "https://netbox.example.com", "api_token": "token"}
    )
    with patch(
        "keep.providers.netbox_provider.netbox_provider.requests.get",
        side_effect=fake_get,
    ):
        services, apps = provider.pull_topology()

    names = {node.service for node in services}
    assert {
        "us-west-2",
        "ai-dc-1",
        "row-a",
        "rack-12",
        "gpu-node-a03",
        "gpu-node-a03-gpu0",
        "10.12.0.0/24",
        "vlan-100",
    }.issubset(names)
    assert apps == {}
    with patch(
        "keep.providers.netbox_provider.netbox_provider.requests.get",
        side_effect=fake_get,
    ):
        assert provider.validate_scopes()["dcim_read"] is True


def test_pagination_follows_next_link():
    provider = _provider(
        {"netbox_url": "https://netbox.example.com", "api_token": "token"}
    )
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        if "offset=1000" in url:
            resp.json.return_value = _page([{"slug": "site-b", "name": "site-b"}])
        else:
            resp.json.return_value = _page(
                [{"slug": "site-a", "name": "site-a"}],
                next_url="https://netbox.example.com/api/dcim/sites/?limit=1000&offset=1000",
            )
        return resp

    with patch(
        "keep.providers.netbox_provider.netbox_provider.requests.get",
        side_effect=fake_get,
    ):
        results = provider._paginate("/api/dcim/sites/")

    assert [item["slug"] for item in results] == ["site-a", "site-b"]
    assert len(calls) == 2


def test_optional_endpoint_404_is_skipped():
    provider = _provider(
        {"netbox_url": "https://netbox.example.com", "api_token": "token"}
    )

    def fake_get(url, **kwargs):
        response = MagicMock()
        response.status_code = 404
        response.raise_for_status.side_effect = requests.HTTPError(response=response)
        return response

    with patch(
        "keep.providers.netbox_provider.netbox_provider.requests.get",
        side_effect=fake_get,
    ):
        assert provider._paginate_optional("/api/dcim/modules/") == []


def test_webhook_only_install_still_validates():
    provider = _provider(None)
    provider.validate_config()
    assert provider.authentication_config.netbox_url == ""
    assert provider.authentication_config.verify_ssl is True


def test_netbox_docs_cover_topology_sync():
    root = Path(__file__).resolve().parents[1]
    docs = (
        root / "docs" / "providers" / "documentation" / "netbox-provider.mdx"
    ).read_text()
    assert "Syncing DCIM topology" in docs
    assert "gpu_name_pattern" in docs
    assert "{host}-gpu{index}" in docs
    overview = (root / "docs" / "overview" / "servicetopology.mdx").read_text()
    assert "netbox-provider" in overview
    snippet = (
        root / "docs" / "snippets" / "providers" / "netbox-snippet-autogenerated.mdx"
    ).read_text()
    assert "pulls [topology]" in snippet


def test_local_compose_and_mock_ui_wire_netbox():
    root = Path(__file__).resolve().parents[1]
    compose = (
        root / "backend" / "services" / "provider-mock" / "docker-compose.yml"
    ).read_text()
    assert "netboxcommunity/netbox" in compose
    assert "8000:8080" in compose
    assert "SUPERUSER_API_TOKEN" in compose
    assert "KEEP_NETBOX_URL" in compose
    html = (
        root / "backend" / "services" / "provider-mock" / "app" / "static" / "index.html"
    ).read_text()
    assert "netboxConfigureKeep" in html
    assert "Configure Keep with NetBox" in html
    mock_docs = (root / "docs" / "development" / "provider-mock.mdx").read_text()
    assert "Configure Keep with NetBox" in mock_docs
    gpu_docs = (root / "docs" / "overview" / "nvidia-gpu-topology.mdx").read_text()
    assert "Configure Keep with NetBox" in gpu_docs
    netbox_docs = (
        root / "docs" / "providers" / "documentation" / "netbox-provider.mdx"
    ).read_text()
    assert "localhost:8000" in netbox_docs
    makefile = (root / "Makefile").read_text()
    assert "http://localhost:8000" in makefile
