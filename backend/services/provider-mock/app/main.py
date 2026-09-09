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
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, HttpUrl

from app.payloads import (
    GRAFANA_CORRELATION_RULE,
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
PORT = int(os.environ.get("PORT", "8099"))

# In-memory registry of providers installed into Keep via this mock.
_registry: dict[ProviderKey, dict[str, Any]] = {}
_event_log: deque[dict[str, Any]] = deque(maxlen=100)

app = FastAPI(
    title="Keep Provider Mock",
    description=(
        "Mock Grafana / Mimir Alertmanager / VictoriaMetrics webhooks, "
        "plus Temporal provider registration against local Docker Compose Temporal"
    ),
    version="1.1.0",
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
    """Create correlation rule (if missing) and send both Grafana mock payloads."""

    provider_id: str | None = None
    create_rule: bool = True
    status: Literal["firing", "resolved"] = "firing"

def _log(entry: dict[str, Any]) -> None:
    entry["ts"] = time.time()
    _event_log.appendleft(entry)


def _keep_headers(api_key: str) -> dict[str, str]:
    return {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


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
        scenarios.append(
            {
                **{k: item[k] for k in ("id", "label", "description")},
                "shared_labels": {
                    "service": item["builder_kwargs"]["service"],
                    "cluster": item["builder_kwargs"]["cluster"],
                    "host": item["builder_kwargs"]["host"],
                },
                "payload": payload,
            }
        )
    return {
        "scenarios": scenarios,
        "correlation_rule": GRAFANA_CORRELATION_RULE,
        "ui_hint": {
            "source_filter_value": "grafana",
            "group_by": "labels.service",
            "threshold": 2,
            "cel": GRAFANA_CORRELATION_RULE["celQuery"],
        },
    }


@app.post("/api/grafana/create-incident-demo")
async def grafana_create_incident_demo(
    body: GrafanaIncidentDemoRequest,
) -> dict[str, Any]:
    """Ensure the payments correlation rule exists, then fire payload A + B."""
    import asyncio
    import uuid as uuid_mod

    keep_base = str(body.keep_api_url).rstrip("/")
    headers = _keep_headers(body.keep_api_key)
    rule_result: dict[str, Any] | None = None
    run_id = uuid_mod.uuid4().hex[:8]

    if body.create_rule:
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
                        if (r.get("name") or r.get("ruleName"))
                        == GRAFANA_CORRELATION_RULE["ruleName"]
                    ),
                    None,
                )
                if found:
                    rule_result = {"action": "exists", "rule": found}
                else:
                    created = await client.post(
                        f"{keep_base}/rules",
                        headers=headers,
                        json=GRAFANA_CORRELATION_RULE,
                    )
                    if created.status_code >= 400:
                        try:
                            detail = created.json()
                        except Exception:
                            detail = created.text
                        raise HTTPException(
                            status_code=created.status_code, detail=detail
                        )
                    rule_result = {"action": "created", "rule": created.json()}
                    _log(
                        {
                            "action": "create-rule",
                            "provider": "grafana",
                            "ok": True,
                            "rule": GRAFANA_CORRELATION_RULE["ruleName"],
                        }
                    )
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502, detail=f"Failed to manage correlation rule: {exc}"
            ) from exc

    provider_id = body.provider_id or (_registry.get("grafana") or {}).get(
        "keep_provider_id"
    )
    send_results = []
    for idx, scenario_id in enumerate(("cpu", "memory")):
        # Space out sends so Keep's async event workers don't race two incidents
        # for the same grouping fingerprint.
        if idx > 0:
            await asyncio.sleep(4)
        payload = build_grafana_scenario_payload(
            scenario_id, status=body.status, run_id=run_id
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
