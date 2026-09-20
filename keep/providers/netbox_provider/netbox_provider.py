"""
NetBox combines IP address management (IPAM) and datacenter infrastructure management (DCIM)
with powerful APIs and extensions, serving as the ideal "source of truth" for network automation.
"""

import dataclasses
from typing import Optional
from urllib.parse import urljoin

import pydantic
import requests

from keep.api.models.alert import AlertDto
from keep.api.models.db.topology import TopologyServiceInDto
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseTopologyProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.netbox_provider.topology import (
    DEFAULT_GPU_PATTERN,
    NetboxInventory,
    build_topology_services,
)


@pydantic.dataclasses.dataclass
class NetboxProviderAuthConfig:
    """NetBox authentication configuration."""

    netbox_url: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "NetBox base URL (required to pull DCIM topology)",
            "hint": "e.g. https://netbox.example.com",
            "sensitive": False,
        },
    )
    api_token: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "NetBox API token with DCIM/IPAM read permissions",
            "hint": "NetBox → Admin → API Tokens",
            "sensitive": True,
        },
    )
    verify_ssl: bool = dataclasses.field(
        default=True,
        metadata={
            "required": False,
            "description": "Verify TLS certificates when calling the NetBox API",
            "sensitive": False,
            "type": "switch",
        },
    )
    gpu_name_pattern: str = dataclasses.field(
        default=DEFAULT_GPU_PATTERN,
        metadata={
            "required": False,
            "description": "Regex matching GPU inventory items and modules",
            "hint": "Matches name, role, part ID, and manufacturer",
            "sensitive": False,
        },
    )


class NetboxProvider(BaseTopologyProvider):
    """
    Ingest NetBox webhook events and pull DCIM/IPAM topology into Keep.
    """

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
  To send alerts from NetBox to Keep, Use the following webhook url to configure NetBox send alerts to Keep:

  1. In NetBox, go to Webhooks under Operations.
  2. Create a new webhook with URL as {keep_webhook_api_url} and request method as POST.
  3. Disable SSL verification.
  4. Add 'X-API-KEY' as the request header with the value as {api_key}.
  5. Save the webhook.
  6. Go to Event Rules and create a new rule and select the webhook created in step 2 to receive alerts.
  """

    PROVIDER_DISPLAY_NAME = "NetBox"
    PROVIDER_TAGS = ["alert", "topology"]
    PROVIDER_CATEGORY = ["Cloud Infrastructure", "Monitoring"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="dcim_read",
            description="Read DCIM and IPAM via the NetBox API (required to sync topology).",
            mandatory=False,
            documentation_url="https://netboxlabs.com/docs/netbox/en/stable/integrations/rest-api/",
            alias="DCIM/IPAM read",
        ),
    ]

    PAGE_LIMIT = 1000
    REQUEST_TIMEOUT = 30
    REQUIRED_ENDPOINTS = (
        "/api/dcim/regions/",
        "/api/dcim/sites/",
        "/api/dcim/locations/",
        "/api/dcim/racks/",
        "/api/dcim/devices/",
    )
    OPTIONAL_ENDPOINTS = (
        "/api/dcim/inventory-items/",
        "/api/dcim/modules/",
        "/api/ipam/prefixes/",
        "/api/ipam/vlans/",
    )

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """No persistent resources to dispose."""
        pass

    def validate_config(self):
        """
        Validates required configuration for NetBox's provider.
        """
        self.authentication_config = NetboxProviderAuthConfig(
            **(self.config.authentication or {})
        )

    @property
    def _host(self) -> str:
        return (self.authentication_config.netbox_url or "").rstrip("/")

    @property
    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        token = (self.authentication_config.api_token or "").strip()
        if token:
            headers["Authorization"] = f"Token {token}"
        return headers

    def _topology_configured(self) -> bool:
        return bool(self._host and (self.authentication_config.api_token or "").strip())

    def validate_scopes(self) -> dict[str, bool | str]:
        if not self._topology_configured():
            return {
                "dcim_read": (
                    "NetBox URL and API token are not configured; "
                    "webhook ingest still works. Add them to pull topology."
                )
            }
        try:
            self._paginate("/api/dcim/sites/", limit=1)
            return {"dcim_read": True}
        except Exception as exc:
            self.logger.exception("Failed to validate NetBox DCIM read scope")
            return {"dcim_read": str(exc)}

    def _request(self, url: str, params: Optional[dict] = None) -> dict:
        response = requests.get(
            url,
            headers=self._headers,
            params=params,
            timeout=self.REQUEST_TIMEOUT,
            verify=self.authentication_config.verify_ssl,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError(f"Unexpected NetBox response from {url}")
        return payload

    def _paginate(self, path: str, limit: Optional[int] = None) -> list[dict]:
        results: list[dict] = []
        url = urljoin(f"{self._host}/", path.lstrip("/"))
        params: Optional[dict] = {"limit": limit or self.PAGE_LIMIT}
        while url:
            payload = self._request(url, params=params)
            page = payload.get("results")
            if isinstance(page, list):
                results.extend(page)
            elif not page and payload.get("id") is not None:
                results.append(payload)
                break
            next_url = payload.get("next")
            if not next_url:
                break
            url = str(next_url)
            if url.startswith("/"):
                url = urljoin(f"{self._host}/", url.lstrip("/"))
            params = None
        return results

    def _paginate_optional(self, path: str) -> list[dict]:
        try:
            return self._paginate(path)
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status in {403, 404}:
                self.logger.info(
                    "Skipping optional NetBox endpoint",
                    extra={"path": path, "status_code": status},
                )
                return []
            raise

    def _fetch_inventory(self) -> NetboxInventory:
        required = {path: self._paginate(path) for path in self.REQUIRED_ENDPOINTS}
        optional = {
            path: self._paginate_optional(path) for path in self.OPTIONAL_ENDPOINTS
        }
        return NetboxInventory(
            regions=required["/api/dcim/regions/"],
            sites=required["/api/dcim/sites/"],
            locations=required["/api/dcim/locations/"],
            racks=required["/api/dcim/racks/"],
            devices=required["/api/dcim/devices/"],
            inventory_items=optional["/api/dcim/inventory-items/"],
            modules=optional["/api/dcim/modules/"],
            prefixes=optional["/api/ipam/prefixes/"],
            vlans=optional["/api/ipam/vlans/"],
        )

    def pull_topology(self) -> tuple[list[TopologyServiceInDto], dict]:
        """Pull datacenter / row / rack / GPU / network topology from NetBox."""
        if not self._topology_configured():
            self.logger.info(
                "NetBox URL or API token not configured, skipping topology pull"
            )
            return [], {}

        self.logger.info(
            "Pulling topology from NetBox",
            extra={"netbox_url": self._host, "provider_id": self.provider_id},
        )
        inventory = self._fetch_inventory()
        pattern = self.authentication_config.gpu_name_pattern or DEFAULT_GPU_PATTERN
        topology = build_topology_services(
            self.provider_id, inventory, gpu_pattern=pattern
        )
        self.logger.info(
            "NetBox topology pull completed",
            extra={
                "provider_id": self.provider_id,
                "nodes": len(topology),
                "sites": len(inventory.sites),
                "devices": len(inventory.devices),
            },
        )
        return topology, {}

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseTopologyProvider" = None
    ) -> AlertDto:
        data = event.get("data", {})
        snapshots = event.get("snapshots", {})

        alert = AlertDto(
            name=data.get("name", "Could not fetch name"),
            lastReceived=event.get("timestamp"),
            startedAt=data.get("created"),
            model=event.get("model", "Could not fetch model"),
            username=event.get("username", "Could not fetch username"),
            id=event.get("request_id"),
            data=data,
            description=event.get("event", "Could not fetch event"),
            snapshots=snapshots,
            source=["netbox"],
        )

        return alert


if __name__ == "__main__":
    pass
