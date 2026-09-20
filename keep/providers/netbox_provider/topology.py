"""Map NetBox DCIM / IPAM objects onto Keep service topology nodes.

Keep topology is a named-node graph. This mapper turns NetBox regions, sites,
locations (rows), racks, devices, GPU inventory/modules, prefixes, and VLANs
into TopologyServiceInDto records whose `service` ids match alert labels used
by the NVIDIA GPU datacenter demo (region / datacenter / row / rack / host / gpu_id).
"""

from __future__ import annotations

import ipaddress
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from keep.api.models.db.topology import TopologyServiceInDto

logger = logging.getLogger(__name__)

DEFAULT_GPU_PATTERN = (
    r"gpu|nvidia|h100|h200|a100|a800|l40s?|\bl4\b|tesla|mig|b200|gb200|blackwell"
)

PROTOCOL_LOCATED_IN = "located-in"
PROTOCOL_POWER = "power"
PROTOCOL_PCIE = "PCIe"
PROTOCOL_L2 = "L2"
PROTOCOL_L3 = "L3"

GPU_INDEX_RE = re.compile(r"(?:gpu[\s\-_]*)(\d+)\s*$", re.I)

SITE_APP_NAMESPACE = uuid.UUID("9c1f0c6e-6f2a-4c5d-9b11-7e8c2d4a1f90")


@dataclass
class NetboxInventory:
    """Paginated NetBox REST payloads used to build topology."""

    regions: list[dict] = field(default_factory=list)
    sites: list[dict] = field(default_factory=list)
    locations: list[dict] = field(default_factory=list)
    racks: list[dict] = field(default_factory=list)
    devices: list[dict] = field(default_factory=list)
    inventory_items: list[dict] = field(default_factory=list)
    modules: list[dict] = field(default_factory=list)
    prefixes: list[dict] = field(default_factory=list)
    vlans: list[dict] = field(default_factory=list)


def nested_value(obj: Any, *keys: str) -> Optional[str]:
    """Read slug/name/display from a NetBox nested object or a raw string."""
    if obj is None:
        return None
    if isinstance(obj, str):
        return obj or None
    if not isinstance(obj, dict):
        return None
    for key in keys or ("slug", "name", "display"):
        value = obj.get(key)
        if value:
            return str(value)
    return None


def object_service_id(obj: dict, *preferred: str) -> Optional[str]:
    """Stable Keep `service` id: slug, then name, then display."""
    keys = preferred or ("slug", "name", "display")
    return nested_value(obj, *keys)


def object_display_name(obj: dict) -> str:
    return nested_value(obj, "display", "name", "slug") or "unknown"


def _custom_fields(obj: dict) -> dict:
    fields = obj.get("custom_fields") or {}
    return fields if isinstance(fields, dict) else {}


def is_gpu_component(obj: dict, pattern: re.Pattern[str]) -> bool:
    """True when an inventory item / module looks like a GPU."""
    haystacks: list[str] = []
    for key in ("name", "label", "part_id", "description", "serial"):
        value = obj.get(key)
        if value:
            haystacks.append(str(value))
    for nested_key in ("role", "manufacturer"):
        nested = obj.get(nested_key)
        for attr in ("slug", "name", "display"):
            value = nested_value(nested, attr) if nested else None
            if value:
                haystacks.append(value)
    module_type = obj.get("module_type") or {}
    if isinstance(module_type, dict):
        model = module_type.get("model") or module_type.get("display")
        if model:
            haystacks.append(str(model))
        manufacturer = nested_value(module_type.get("manufacturer"), "name", "slug")
        if manufacturer:
            haystacks.append(manufacturer)
    return any(pattern.search(text) for text in haystacks)


def gpu_index_from_name(*names: Optional[str]) -> Optional[int]:
    """Parse a GPU slot index from names like 'GPU 0', 'gpu-1', or 'GPU1'.

    Model numbers such as H100 are ignored so they do not become gpu100.
    """
    for name in names:
        if not name:
            continue
        match = GPU_INDEX_RE.search(str(name).strip())
        if match:
            return int(match.group(1))
    return None


def gpu_service_name(host: str, index: int) -> str:
    return f"{host}-gpu{index}"


def address_in_prefix(address: Optional[str], prefix: Optional[str]) -> bool:
    if not address or not prefix:
        return False
    try:
        ip = ipaddress.ip_interface(address).ip
        network = ipaddress.ip_network(prefix, strict=False)
        return ip in network
    except ValueError:
        return False


def site_application_id(site_slug: str) -> uuid.UUID:
    return uuid.uuid5(SITE_APP_NAMESPACE, f"keep.netbox.site.{site_slug}")


def _ensure_node(
    nodes: dict[str, TopologyServiceInDto],
    *,
    provider_id: str,
    service: str,
    display_name: str,
    category: str,
    description: Optional[str] = None,
    environment: str = "unknown",
    tags: Optional[list[str]] = None,
    ip_address: Optional[str] = None,
    manufacturer: Optional[str] = None,
    namespace: Optional[str] = None,
    application_relations: Optional[dict[uuid.UUID, str]] = None,
) -> TopologyServiceInDto:
    existing = nodes.get(service)
    if existing:
        if application_relations:
            existing.application_relations = {
                **(existing.application_relations or {}),
                **application_relations,
            }
        return existing
    node = TopologyServiceInDto(
        source_provider_id=provider_id,
        service=service,
        display_name=display_name,
        category=category,
        description=description,
        environment=environment,
        tags=tags or ["netbox", category],
        ip_address=ip_address,
        manufacturer=manufacturer,
        namespace=namespace,
        application_relations=application_relations,
        dependencies={},
    )
    nodes[service] = node
    return node


def _depend(node: TopologyServiceInDto, target: Optional[str], protocol: str) -> None:
    if not target or target == node.service:
        return
    node.dependencies[target] = protocol


def _site_apps(sites: list[dict]) -> dict[str, tuple[uuid.UUID, str]]:
    apps: dict[str, tuple[uuid.UUID, str]] = {}
    for site in sites:
        slug = object_service_id(site)
        if not slug:
            continue
        name = object_display_name(site)
        apps[slug] = (site_application_id(slug), f"NetBox {name}")
    return apps


def _app_for_site(
    site_slug: Optional[str], apps: dict[str, tuple[uuid.UUID, str]]
) -> Optional[dict[uuid.UUID, str]]:
    if not site_slug or site_slug not in apps:
        return None
    app_id, app_name = apps[site_slug]
    return {app_id: app_name}


def build_topology_services(
    provider_id: str,
    inventory: NetboxInventory,
    gpu_pattern: str = DEFAULT_GPU_PATTERN,
) -> list[TopologyServiceInDto]:
    """Convert a NetBox inventory snapshot into Keep topology nodes."""
    pattern = re.compile(gpu_pattern, re.I)
    nodes: dict[str, TopologyServiceInDto] = {}
    site_apps = _site_apps(inventory.sites)

    for region in inventory.regions:
        service = object_service_id(region)
        if not service:
            continue
        node = _ensure_node(
            nodes,
            provider_id=provider_id,
            service=service,
            display_name=object_display_name(region),
            category="region",
            description=region.get("description") or f"NetBox region {service}",
            environment=service,
            tags=["netbox", "region"],
            namespace=service,
        )
        parent = nested_value(region.get("parent"), "slug", "name")
        _depend(node, parent, PROTOCOL_LOCATED_IN)

    for site in inventory.sites:
        service = object_service_id(site)
        if not service:
            continue
        region_id = nested_value(site.get("region"), "slug", "name")
        node = _ensure_node(
            nodes,
            provider_id=provider_id,
            service=service,
            display_name=object_display_name(site),
            category="datacenter",
            description=site.get("description") or f"NetBox site {service}",
            environment=region_id or service,
            tags=["netbox", "datacenter"],
            namespace=service,
            application_relations=_app_for_site(service, site_apps),
        )
        _depend(node, region_id, PROTOCOL_LOCATED_IN)

    for location in inventory.locations:
        service = object_service_id(location)
        if not service:
            continue
        site_slug = nested_value(location.get("site"), "slug", "name")
        parent = nested_value(location.get("parent"), "slug", "name")
        node = _ensure_node(
            nodes,
            provider_id=provider_id,
            service=service,
            display_name=object_display_name(location),
            category="row",
            description=location.get("description") or f"NetBox location {service}",
            environment=site_slug or "unknown",
            tags=["netbox", "row"],
            namespace=site_slug,
            application_relations=_app_for_site(site_slug, site_apps),
        )
        _depend(node, parent or site_slug, PROTOCOL_LOCATED_IN)

    for rack in inventory.racks:
        service = object_service_id(rack, "slug", "name", "display")
        if not service:
            continue
        site_slug = nested_value(rack.get("site"), "slug", "name")
        location_id = nested_value(rack.get("location"), "slug", "name")
        node = _ensure_node(
            nodes,
            provider_id=provider_id,
            service=service,
            display_name=object_display_name(rack),
            category="rack",
            description=rack.get("description") or f"NetBox rack {service}",
            environment=site_slug or "unknown",
            tags=["netbox", "rack"],
            namespace=site_slug,
            application_relations=_app_for_site(site_slug, site_apps),
        )
        _depend(node, location_id or site_slug, PROTOCOL_LOCATED_IN)

    host_ips: dict[str, str] = {}
    for device in inventory.devices:
        service = object_service_id(device, "name", "display", "slug")
        if not service:
            continue
        site_slug = nested_value(device.get("site"), "slug", "name")
        rack_id = nested_value(device.get("rack"), "slug", "name", "display")
        location_id = nested_value(device.get("location"), "slug", "name")
        primary_ip = nested_value(
            device.get("primary_ip4") or device.get("primary_ip"), "address"
        )
        ip_only = primary_ip.split("/")[0] if primary_ip else None
        if ip_only:
            host_ips[service] = primary_ip or ip_only
        manufacturer = nested_value(
            (device.get("device_type") or {}).get("manufacturer")
            if isinstance(device.get("device_type"), dict)
            else None,
            "name",
            "slug",
        )
        node = _ensure_node(
            nodes,
            provider_id=provider_id,
            service=service,
            display_name=object_display_name(device),
            category="host",
            description=device.get("description") or f"NetBox device {service}",
            environment=site_slug or "unknown",
            tags=["netbox", "host"],
            ip_address=ip_only,
            manufacturer=manufacturer,
            namespace=site_slug,
            application_relations=_app_for_site(site_slug, site_apps),
        )
        parent = rack_id or location_id or site_slug
        _depend(node, parent, PROTOCOL_POWER if rack_id else PROTOCOL_LOCATED_IN)

    _add_gpu_components(
        nodes,
        provider_id=provider_id,
        inventory=inventory,
        pattern=pattern,
        site_apps=site_apps,
    )
    hosts_with_gpus = {
        dep
        for node in nodes.values()
        if node.category == "gpu"
        for dep in node.dependencies
    }
    for device in inventory.devices:
        host = object_service_id(device, "name", "display", "slug")
        if not host or host in hosts_with_gpus:
            continue
        site_slug = nested_value(device.get("site"), "slug", "name")
        manufacturer = nested_value(
            (device.get("device_type") or {}).get("manufacturer")
            if isinstance(device.get("device_type"), dict)
            else None,
            "name",
            "slug",
        )
        _add_synthetic_gpus(
            nodes,
            provider_id=provider_id,
            host=host,
            device=device,
            site_slug=site_slug,
            site_apps=site_apps,
            manufacturer=manufacturer,
        )

    for vlan in inventory.vlans:
        service = _vlan_service_id(vlan)
        if not service:
            continue
        site_slug = nested_value(vlan.get("site"), "slug", "name")
        vid = vlan.get("vid")
        node = _ensure_node(
            nodes,
            provider_id=provider_id,
            service=service,
            display_name=object_display_name(vlan),
            category="network",
            description=vlan.get("description") or f"VLAN {vid}",
            environment=site_slug or "unknown",
            tags=["netbox", "network", "vlan"],
            namespace=site_slug,
            application_relations=_app_for_site(site_slug, site_apps),
        )
        _depend(node, site_slug, PROTOCOL_LOCATED_IN)

    for prefix in inventory.prefixes:
        cidr = prefix.get("prefix")
        if not cidr:
            continue
        service = str(cidr)
        site_slug = nested_value(prefix.get("site"), "slug", "name")
        vlan_id = _vlan_service_id(prefix.get("vlan") or {})
        node = _ensure_node(
            nodes,
            provider_id=provider_id,
            service=service,
            display_name=prefix.get("description") or service,
            category="network",
            description=prefix.get("description") or f"Prefix {service}",
            environment=site_slug or "unknown",
            tags=["netbox", "network", "prefix"],
            namespace=site_slug,
            application_relations=_app_for_site(site_slug, site_apps),
        )
        _depend(node, site_slug, PROTOCOL_LOCATED_IN)
        _depend(node, vlan_id, PROTOCOL_L2)
        for host, address in host_ips.items():
            host_node = nodes.get(host)
            if host_node and address_in_prefix(address, service):
                _depend(host_node, service, PROTOCOL_L3)

    logger.info(
        "Built NetBox topology",
        extra={"provider_id": provider_id, "nodes": len(nodes)},
    )
    return list(nodes.values())


def _vlan_service_id(vlan: dict) -> Optional[str]:
    if not vlan:
        return None
    vid = vlan.get("vid")
    slug = nested_value(vlan, "slug", "name")
    if vid is not None:
        return f"vlan-{vid}"
    if slug:
        return f"vlan-{slug}"
    return None


def _add_synthetic_gpus(
    nodes: dict[str, TopologyServiceInDto],
    *,
    provider_id: str,
    host: str,
    device: dict,
    site_slug: Optional[str],
    site_apps: dict[str, tuple[uuid.UUID, str]],
    manufacturer: Optional[str],
) -> None:
    raw_count = _custom_fields(device).get("gpu_count")
    try:
        count = int(raw_count)
    except (TypeError, ValueError):
        return
    if count <= 0:
        return
    for index in range(count):
        _add_gpu_node(
            nodes,
            provider_id=provider_id,
            host=host,
            index=index,
            display_name=f"GPU {index} @ {host}",
            description=f"Synthetic GPU {index} from NetBox custom field gpu_count",
            site_slug=site_slug,
            site_apps=site_apps,
            manufacturer=manufacturer,
        )


def _add_gpu_components(
    nodes: dict[str, TopologyServiceInDto],
    *,
    provider_id: str,
    inventory: NetboxInventory,
    pattern: re.Pattern[str],
    site_apps: dict[str, tuple[uuid.UUID, str]],
) -> None:
    per_host_index: dict[str, int] = {}

    def next_index(host: str, hinted: Optional[int]) -> int:
        if hinted is not None:
            per_host_index[host] = max(per_host_index.get(host, -1), hinted)
            return hinted
        current = per_host_index.get(host, -1) + 1
        per_host_index[host] = current
        return current

    gpu_modules = [
        item for item in inventory.modules if is_gpu_component(item, pattern)
    ]
    gpu_items = [
        item for item in inventory.inventory_items if is_gpu_component(item, pattern)
    ]
    # Prefer modules (PCIe / GPU trays) when both exist so we do not duplicate.
    components = gpu_modules or gpu_items

    for item in components:
        host = nested_value(item.get("device"), "name", "display", "slug")
        if not host or host not in nodes:
            continue
        bay = item.get("module_bay") if isinstance(item.get("module_bay"), dict) else {}
        hinted = gpu_index_from_name(
            item.get("name"),
            item.get("label"),
            nested_value(bay, "name") if bay else None,
        )
        index = next_index(host, hinted)
        manufacturer = nested_value(item.get("manufacturer"), "name", "slug")
        if not manufacturer:
            module_type = (
                item.get("module_type")
                if isinstance(item.get("module_type"), dict)
                else {}
            )
            manufacturer = nested_value(
                module_type.get("manufacturer") if module_type else None, "name", "slug"
            )
        host_node = nodes[host]
        _add_gpu_node(
            nodes,
            provider_id=provider_id,
            host=host,
            index=index,
            display_name=item.get("display")
            or item.get("name")
            or f"GPU {index} @ {host}",
            description=item.get("description")
            or item.get("part_id")
            or f"GPU {index} on {host}",
            site_slug=host_node.namespace,
            site_apps=site_apps,
            manufacturer=manufacturer or host_node.manufacturer,
        )


def _add_gpu_node(
    nodes: dict[str, TopologyServiceInDto],
    *,
    provider_id: str,
    host: str,
    index: int,
    display_name: str,
    description: str,
    site_slug: Optional[str],
    site_apps: dict[str, tuple[uuid.UUID, str]],
    manufacturer: Optional[str],
) -> None:
    service = gpu_service_name(host, index)
    node = _ensure_node(
        nodes,
        provider_id=provider_id,
        service=service,
        display_name=display_name,
        category="gpu",
        description=description,
        environment=site_slug or "unknown",
        tags=["netbox", "gpu", host],
        manufacturer=manufacturer,
        namespace=site_slug,
        application_relations=_app_for_site(site_slug, site_apps),
    )
    _depend(node, host, PROTOCOL_PCIE)
