"""
Temporal Provider starts and manages Temporal workflows from Keep workflows.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import uuid
from typing import Any, Optional

import pydantic

import chevron

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.models.provider_method import ProviderMethod

DEFAULT_WORKFLOW_CATALOG = [
    {
        "id": "remediate-incident",
        "name": "Remediate Incident",
        "description": "Start a Temporal remediation workflow for a Keep incident",
        "workflow_type": "RemediateIncident",
        "task_queue": "keep-ops",
        "workflow_id_template": "incident-{{incident.id}}-{{catalog.id}}",
        "input_mapping": {
            "incident_id": "id",
            "name": "name",
            "severity": "severity",
            "status": "status",
            "services": "services",
        },
    }
]


@pydantic.dataclasses.dataclass
class TemporalProviderAuthConfig:
    """Temporal authentication and connection configuration."""

    address: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Temporal frontend address (host:port)",
            "hint": "localhost:7233 or your-namespace.a1b2c.tmprl.cloud:7233",
        }
    )

    namespace: str = dataclasses.field(
        default="default",
        metadata={
            "required": False,
            "description": "Temporal namespace",
            "hint": "default, or <namespace_id>.<account_id> for Temporal Cloud",
        },
    )

    api_key: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Temporal Cloud API key (enables TLS automatically)",
            "sensitive": True,
        },
    )

    tls: bool = dataclasses.field(
        default=False,
        metadata={
            "required": False,
            "description": "Enable TLS (required for Temporal Cloud; auto-enabled when api_key is set)",
            "type": "switch",
        },
    )

    tls_client_cert: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "mTLS client certificate PEM contents",
            "sensitive": True,
            "type": "textarea",
        },
    )

    tls_client_key: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "mTLS client private key PEM contents",
            "sensitive": True,
            "type": "textarea",
        },
    )

    tls_server_root_ca_cert: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Optional server CA certificate PEM contents for mTLS",
            "sensitive": True,
            "type": "textarea",
        },
    )

    workflow_catalog: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": (
                "Keep-managed Temporal workflow catalog as JSON array. "
                "Each entry needs id, name, workflow_type, task_queue; "
                "optional description, workflow_id_template, input_mapping."
            ),
            "hint": json.dumps(DEFAULT_WORKFLOW_CATALOG, indent=2),
            "type": "textarea",
            "placeholder": "Paste JSON array of catalog workflows",
        },
    )


class TemporalProvider(BaseProvider):
    """Start and manage Temporal workflows from Keep actions and steps."""

    PROVIDER_DISPLAY_NAME = "Temporal"
    PROVIDER_CATEGORY = ["Orchestration"]
    PROVIDER_TAGS = ["data"]
    provider_description = (
        "Start Temporal workflows when Keep alerts or incidents are received."
    )

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connect",
            description="Connect to the Temporal frontend and access the namespace",
            mandatory=True,
            alias="Connect",
        ),
    ]

    PROVIDER_METHODS = [
        ProviderMethod(
            name="get_workflow_catalog",
            func_name="get_workflow_catalog",
            description="List Keep-managed Temporal workflows available to start",
            type="view",
        ),
        ProviderMethod(
            name="start_workflow_from_catalog",
            func_name="start_workflow_from_catalog",
            description="Start a catalog Temporal workflow and link it to an incident",
            type="action",
        ),
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.authentication_config: TemporalProviderAuthConfig

    def validate_config(self):
        self.authentication_config = TemporalProviderAuthConfig(
            **self.config.authentication
        )
        # Fail fast if catalog JSON is present but invalid.
        self._parse_workflow_catalog()

    def dispose(self):
        """Temporal clients are created per-call; nothing to dispose."""
        pass

    def validate_scopes(self) -> dict[str, bool | str]:
        try:
            self._run_async(self._validate_connection())
            return {"connect": True}
        except Exception as exc:
            self.logger.exception("Failed to validate Temporal connection")
            return {"connect": str(exc)}

    def get_workflow_catalog(self) -> list[dict]:
        """
        Return the Keep-managed Temporal workflow catalog.

        Used by the incident Workflows UI to show startable Temporal workflows.
        """
        return self._parse_workflow_catalog()

    def start_workflow_from_catalog(
        self, catalog_id: str, incident: dict | str | None = None
    ) -> dict:
        """
        Start a Temporal workflow defined in the Keep-managed catalog.

        Args:
            catalog_id: Catalog entry id (not Temporal workflow id).
            incident: Incident payload (dict or JSON string) used for input_mapping
                and workflow_id_template rendering.
        """
        entry = self._get_catalog_entry(catalog_id)
        incident_data = self._normalize_incident_payload(incident)
        workflow_input = self._build_input_from_mapping(
            entry.get("input_mapping") or {}, incident_data
        )
        workflow_id = self._render_workflow_id(
            entry.get("workflow_id_template"),
            incident_data=incident_data,
            catalog_entry=entry,
        )

        result = self._notify(
            operation="start_workflow",
            workflow_type=entry["workflow_type"],
            task_queue=entry["task_queue"],
            workflow_id=workflow_id,
            arg=workflow_input,
        )
        return {
            **result,
            "catalog_id": entry["id"],
            "catalog_name": entry.get("name") or entry["id"],
            "incident_id": incident_data.get("id"),
            "input": workflow_input,
        }

    async def _validate_connection(self):
        client = await self._connect()
        # Lightweight check: ensure the client can talk to the service.
        check_health = getattr(getattr(client, "service_client", None), "check_health", None)
        if callable(check_health):
            await check_health()
            return True
        async for _ in client.list_workflows(page_size=1):
            break
        return True

    def _notify(
        self,
        workflow_type: str = "",
        task_queue: str = "",
        workflow_id: Optional[str] = None,
        args: Any = None,
        arg: Any = None,
        operation: str = "start_workflow",
        signal_name: Optional[str] = None,
        signal_args: Any = None,
        reason: Optional[str] = None,
        run_id: Optional[str] = None,
        **kwargs,
    ):
        """
        Temporal action used from Keep workflow `actions`.

        Supported operations:
          - start_workflow (default)
          - signal_workflow
          - cancel_workflow
          - terminate_workflow
        """
        operation = (operation or "start_workflow").lower()
        if operation == "start_workflow":
            if not workflow_type:
                raise ProviderException("workflow_type is required to start a workflow")
            if not task_queue:
                raise ProviderException("task_queue is required to start a workflow")
            return self._run_async(
                self._start_workflow(
                    workflow_type=workflow_type,
                    task_queue=task_queue,
                    workflow_id=workflow_id,
                    args=args,
                    arg=arg,
                )
            )
        if not workflow_id:
            raise ProviderException(f"workflow_id is required for operation '{operation}'")

        if operation == "signal_workflow":
            if not signal_name:
                raise ProviderException("signal_name is required for signal_workflow")
            return self._run_async(
                self._signal_workflow(
                    workflow_id=workflow_id,
                    run_id=run_id,
                    signal_name=signal_name,
                    signal_args=signal_args,
                )
            )
        if operation == "cancel_workflow":
            return self._run_async(
                self._cancel_workflow(
                    workflow_id=workflow_id, run_id=run_id, reason=reason
                )
            )
        if operation == "terminate_workflow":
            return self._run_async(
                self._terminate_workflow(
                    workflow_id=workflow_id, run_id=run_id, reason=reason
                )
            )

        raise ProviderException(
            f"Unsupported Temporal notify operation: {operation}. "
            "Use start_workflow, signal_workflow, cancel_workflow, or terminate_workflow."
        )

    def _query(
        self,
        operation: str = "describe_workflow",
        workflow_id: str = "",
        run_id: Optional[str] = None,
        query_name: Optional[str] = None,
        query_args: Any = None,
        query: Optional[str] = None,
        page_size: int = 20,
        **kwargs,
    ):
        """
        Temporal step used from Keep workflow `steps`.

        Supported operations:
          - describe_workflow (default)
          - query_workflow
          - list_workflows
        """
        operation = (operation or "describe_workflow").lower()
        if operation == "list_workflows":
            return self._run_async(
                self._list_workflows(query=query, page_size=page_size)
            )

        if not workflow_id:
            raise ProviderException(f"workflow_id is required for operation '{operation}'")

        if operation == "describe_workflow":
            return self._run_async(
                self._describe_workflow(workflow_id=workflow_id, run_id=run_id)
            )
        if operation == "query_workflow":
            if not query_name:
                raise ProviderException("query_name is required for query_workflow")
            return self._run_async(
                self._query_workflow(
                    workflow_id=workflow_id,
                    run_id=run_id,
                    query_name=query_name,
                    query_args=query_args,
                )
            )

        raise ProviderException(
            f"Unsupported Temporal query operation: {operation}. "
            "Use describe_workflow, query_workflow, or list_workflows."
        )

    async def _connect(self):
        try:
            from temporalio.client import Client, TLSConfig
        except ImportError as exc:
            raise ProviderException(
                "temporalio package is required for the Temporal provider. "
                "Install it with: poetry add temporalio"
            ) from exc

        connect_kwargs: dict[str, Any] = {
            "namespace": self.authentication_config.namespace or "default",
        }

        if self.authentication_config.api_key:
            connect_kwargs["api_key"] = self.authentication_config.api_key

        tls_config = self._build_tls_config(TLSConfig)
        if tls_config is not None:
            connect_kwargs["tls"] = tls_config

        try:
            return await Client.connect(
                self.authentication_config.address, **connect_kwargs
            )
        except Exception as exc:
            raise ProviderException(
                f"Failed to connect to Temporal at {self.authentication_config.address}: {exc}"
            ) from exc

    def _build_tls_config(self, TLSConfig):
        auth = self.authentication_config
        has_mtls = bool(auth.tls_client_cert and auth.tls_client_key)

        if has_mtls:
            return TLSConfig(
                client_cert=auth.tls_client_cert.encode("utf-8"),
                client_private_key=auth.tls_client_key.encode("utf-8"),
                server_root_ca_cert=(
                    auth.tls_server_root_ca_cert.encode("utf-8")
                    if auth.tls_server_root_ca_cert
                    else None
                ),
            )

        if auth.api_key:
            # API key auth requires TLS; True uses system defaults.
            return True

        if auth.tls:
            return True

        return None

    async def _start_workflow(
        self,
        workflow_type: str,
        task_queue: str,
        workflow_id: Optional[str],
        args: Any,
        arg: Any,
    ):
        client = await self._connect()
        workflow_id = workflow_id or f"keep-{uuid.uuid4()}"
        normalized_args = self._normalize_args(args, arg)

        self.logger.info(
            "Starting Temporal workflow",
            extra={
                "workflow_type": workflow_type,
                "workflow_id": workflow_id,
                "task_queue": task_queue,
                "namespace": self.authentication_config.namespace,
            },
        )

        try:
            if normalized_args is None:
                handle = await client.start_workflow(
                    workflow_type,
                    id=workflow_id,
                    task_queue=task_queue,
                )
            elif isinstance(normalized_args, list):
                handle = await client.start_workflow(
                    workflow_type,
                    args=normalized_args,
                    id=workflow_id,
                    task_queue=task_queue,
                )
            else:
                handle = await client.start_workflow(
                    workflow_type,
                    normalized_args,
                    id=workflow_id,
                    task_queue=task_queue,
                )
        except Exception as exc:
            raise ProviderException(
                f"Failed to start Temporal workflow '{workflow_type}': {exc}"
            ) from exc

        return {
            "workflow_id": handle.id,
            "run_id": handle.result_run_id,
            "task_queue": task_queue,
            "workflow_type": workflow_type,
            "namespace": self.authentication_config.namespace,
        }

    async def _signal_workflow(
        self,
        workflow_id: str,
        run_id: Optional[str],
        signal_name: str,
        signal_args: Any,
    ):
        client = await self._connect()
        handle = client.get_workflow_handle(workflow_id, run_id=run_id)
        normalized = self._normalize_args(signal_args, None)
        try:
            if normalized is None:
                await handle.signal(signal_name)
            elif isinstance(normalized, list):
                await handle.signal(signal_name, args=normalized)
            else:
                await handle.signal(signal_name, normalized)
        except Exception as exc:
            raise ProviderException(
                f"Failed to signal Temporal workflow '{workflow_id}': {exc}"
            ) from exc
        return {
            "workflow_id": workflow_id,
            "run_id": run_id,
            "signal_name": signal_name,
            "status": "signaled",
        }

    async def _cancel_workflow(
        self, workflow_id: str, run_id: Optional[str], reason: Optional[str]
    ):
        client = await self._connect()
        handle = client.get_workflow_handle(workflow_id, run_id=run_id)
        try:
            await handle.cancel()
        except Exception as exc:
            raise ProviderException(
                f"Failed to cancel Temporal workflow '{workflow_id}': {exc}"
            ) from exc
        return {
            "workflow_id": workflow_id,
            "run_id": run_id,
            "status": "cancel_requested",
            "reason": reason,
        }

    async def _terminate_workflow(
        self, workflow_id: str, run_id: Optional[str], reason: Optional[str]
    ):
        client = await self._connect()
        handle = client.get_workflow_handle(workflow_id, run_id=run_id)
        try:
            await handle.terminate(reason=reason or "Terminated by Keep")
        except Exception as exc:
            raise ProviderException(
                f"Failed to terminate Temporal workflow '{workflow_id}': {exc}"
            ) from exc
        return {
            "workflow_id": workflow_id,
            "run_id": run_id,
            "status": "terminated",
            "reason": reason or "Terminated by Keep",
        }

    async def _describe_workflow(self, workflow_id: str, run_id: Optional[str]):
        client = await self._connect()
        handle = client.get_workflow_handle(workflow_id, run_id=run_id)
        try:
            description = await handle.describe()
        except Exception as exc:
            raise ProviderException(
                f"Failed to describe Temporal workflow '{workflow_id}': {exc}"
            ) from exc

        status = getattr(description, "status", None)
        status_name = getattr(status, "name", None) or str(status)
        return {
            "workflow_id": description.id,
            "run_id": description.run_id,
            "workflow_type": getattr(
                getattr(description, "workflow_type", None), "name", None
            ),
            "task_queue": getattr(description, "task_queue", None),
            "status": status_name,
            "start_time": (
                description.start_time.isoformat()
                if getattr(description, "start_time", None)
                else None
            ),
            "close_time": (
                description.close_time.isoformat()
                if getattr(description, "close_time", None)
                else None
            ),
        }

    async def _query_workflow(
        self,
        workflow_id: str,
        run_id: Optional[str],
        query_name: str,
        query_args: Any,
    ):
        client = await self._connect()
        handle = client.get_workflow_handle(workflow_id, run_id=run_id)
        normalized = self._normalize_args(query_args, None)
        try:
            if normalized is None:
                result = await handle.query(query_name)
            elif isinstance(normalized, list):
                result = await handle.query(query_name, args=normalized)
            else:
                result = await handle.query(query_name, normalized)
        except Exception as exc:
            raise ProviderException(
                f"Failed to query Temporal workflow '{workflow_id}': {exc}"
            ) from exc
        return {
            "workflow_id": workflow_id,
            "run_id": run_id,
            "query_name": query_name,
            "result": self._json_safe(result),
        }

    async def _list_workflows(self, query: Optional[str], page_size: int):
        client = await self._connect()
        workflows = []
        try:
            async for workflow in client.list_workflows(
                query=query, page_size=page_size
            ):
                status = getattr(workflow, "status", None)
                workflows.append(
                    {
                        "workflow_id": workflow.id,
                        "run_id": workflow.run_id,
                        "workflow_type": getattr(
                            getattr(workflow, "workflow_type", None), "name", None
                        ),
                        "status": getattr(status, "name", None) or str(status),
                        "start_time": (
                            workflow.start_time.isoformat()
                            if getattr(workflow, "start_time", None)
                            else None
                        ),
                    }
                )
                if len(workflows) >= page_size:
                    break
        except Exception as exc:
            raise ProviderException(f"Failed to list Temporal workflows: {exc}") from exc
        return {"workflows": workflows, "count": len(workflows), "query": query}

    @staticmethod
    def _normalize_args(args: Any, arg: Any) -> Any:
        if args is not None and arg is not None:
            raise ProviderException("Provide either 'args' or 'arg', not both")
        value = args if args is not None else arg
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value

    def _parse_workflow_catalog(self) -> list[dict]:
        raw = self.authentication_config.workflow_catalog
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            return []

        if isinstance(raw, list):
            catalog = raw
        elif isinstance(raw, str):
            try:
                catalog = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ProviderException(
                    f"workflow_catalog must be valid JSON: {exc}"
                ) from exc
        else:
            raise ProviderException("workflow_catalog must be a JSON array or string")

        if not isinstance(catalog, list):
            raise ProviderException("workflow_catalog must be a JSON array")

        normalized: list[dict] = []
        for index, entry in enumerate(catalog):
            if not isinstance(entry, dict):
                raise ProviderException(
                    f"workflow_catalog[{index}] must be an object"
                )
            catalog_id = entry.get("id")
            workflow_type = entry.get("workflow_type")
            task_queue = entry.get("task_queue")
            if not catalog_id or not workflow_type or not task_queue:
                raise ProviderException(
                    f"workflow_catalog[{index}] requires id, workflow_type, and task_queue"
                )
            normalized.append(
                {
                    "id": str(catalog_id),
                    "name": entry.get("name") or str(catalog_id),
                    "description": entry.get("description") or "",
                    "workflow_type": str(workflow_type),
                    "task_queue": str(task_queue),
                    "workflow_id_template": entry.get("workflow_id_template")
                    or "incident-{{incident.id}}-{{catalog.id}}",
                    "input_mapping": entry.get("input_mapping") or {},
                }
            )
        return normalized

    def _get_catalog_entry(self, catalog_id: str) -> dict:
        if not catalog_id:
            raise ProviderException("catalog_id is required")
        for entry in self._parse_workflow_catalog():
            if entry["id"] == catalog_id:
                return entry
        raise ProviderException(f"Catalog workflow '{catalog_id}' not found")

    @staticmethod
    def _normalize_incident_payload(incident: dict | str | None) -> dict:
        if incident is None:
            return {}
        if isinstance(incident, str):
            try:
                incident = json.loads(incident)
            except json.JSONDecodeError as exc:
                raise ProviderException(
                    f"incident must be a JSON object: {exc}"
                ) from exc
        if not isinstance(incident, dict):
            # Support IncidentDto-like objects.
            if hasattr(incident, "dict"):
                incident = incident.dict()
            else:
                raise ProviderException("incident must be a dict or JSON object")

        # Normalize common nested wrappers.
        if "incident" in incident and isinstance(incident["incident"], dict):
            nested = dict(incident["incident"])
            nested.setdefault("id", incident.get("id"))
            return nested

        normalized = dict(incident)
        # Expose property-like name when only user_generated_name / ai_generated_name exist.
        if "name" not in normalized:
            normalized["name"] = (
                normalized.get("user_generated_name")
                or normalized.get("ai_generated_name")
            )
        if "id" in normalized:
            normalized["id"] = str(normalized["id"])
        if "severity" in normalized and hasattr(normalized["severity"], "value"):
            normalized["severity"] = normalized["severity"].value
        if "status" in normalized and hasattr(normalized["status"], "value"):
            normalized["status"] = normalized["status"].value
        return normalized

    @staticmethod
    def _resolve_incident_path(incident: dict, path: str) -> Any:
        cleaned = path.strip()
        if cleaned.startswith("incident."):
            cleaned = cleaned[len("incident.") :]
        if cleaned.startswith("{{") and cleaned.endswith("}}"):
            cleaned = cleaned.strip("{} ").replace("incident.", "")

        current: Any = incident
        for part in cleaned.split("."):
            if current is None:
                return None
            if isinstance(current, dict):
                current = current.get(part)
            else:
                current = getattr(current, part, None)
        return current

    def _build_input_from_mapping(
        self, input_mapping: dict, incident_data: dict
    ) -> dict:
        if not isinstance(input_mapping, dict):
            raise ProviderException("input_mapping must be an object")
        payload = {}
        for key, path in input_mapping.items():
            if not isinstance(path, str):
                payload[key] = path
                continue
            payload[key] = self._resolve_incident_path(incident_data, path)
        return payload

    def _render_workflow_id(
        self,
        template: Optional[str],
        incident_data: dict,
        catalog_entry: dict,
    ) -> str:
        rendered_template = template or "incident-{{incident.id}}-{{catalog.id}}"
        context = {
            "incident": incident_data,
            "catalog": catalog_entry,
        }
        try:
            workflow_id = chevron.render(rendered_template, context)
        except Exception as exc:
            raise ProviderException(
                f"Failed to render workflow_id_template: {exc}"
            ) from exc
        workflow_id = (workflow_id or "").strip()
        if not workflow_id:
            workflow_id = f"keep-{catalog_entry['id']}-{uuid.uuid4()}"
        return workflow_id

    @staticmethod
    def _json_safe(value: Any) -> Any:
        try:
            json.dumps(value)
            return value
        except TypeError:
            return str(value)

    @staticmethod
    def _run_async(coro):
        """Run an async Temporal SDK call from Keep's sync workflow executor."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        # Already inside an event loop (e.g. FastAPI): run in a fresh loop/thread.
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(asyncio.run, coro).result()


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(tenant_id="singletenant", workflow_id="test")
    config = ProviderConfig(
        authentication={
            "address": os.environ.get("TEMPORAL_ADDRESS", "localhost:7233"),
            "namespace": os.environ.get("TEMPORAL_NAMESPACE", "default"),
            "api_key": os.environ.get("TEMPORAL_API_KEY"),
            "tls": os.environ.get("TEMPORAL_TLS", "false").lower() == "true",
            "workflow_catalog": os.environ.get("TEMPORAL_WORKFLOW_CATALOG"),
        }
    )
    provider = TemporalProvider(
        context_manager=context_manager, provider_id="test", config=config
    )
    print(provider.validate_scopes())
    print(provider.get_workflow_catalog())
