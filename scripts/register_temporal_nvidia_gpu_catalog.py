#!/usr/bin/env python3
"""
Register the RemediateNvidiaGpu Temporal workflow in Keep's catalog.

Usage (API running on localhost:8080 with default mock-admin key):

  python scripts/register_temporal_nvidia_gpu_catalog.py

Env overrides:
  KEEP_API_URL=http://localhost:8080
  KEEP_API_KEY=keepappkey
  TEMPORAL_PROVIDER_ID=   # optional; auto-picks first installed temporal provider
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def _request(method: str, url: str, api_key: str, body: dict | None = None) -> tuple[int, object]:
    data = None
    headers = {"x-api-key": api_key, "Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8") or "null"
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw
        return exc.code, parsed


def main() -> int:
    api_url = os.environ.get("KEEP_API_URL", "http://localhost:8080").rstrip("/")
    api_key = os.environ.get("KEEP_API_KEY", "keepappkey")
    provider_id = os.environ.get("TEMPORAL_PROVIDER_ID")

    if not provider_id:
        status, providers = _request("GET", f"{api_url}/providers", api_key)
        if status != 200:
            print(f"Failed to list providers ({status}): {providers}", file=sys.stderr)
            return 1
        installed = []
        if isinstance(providers, dict):
            installed = providers.get("installed_providers") or providers.get("providers") or []
        elif isinstance(providers, list):
            installed = providers
        temporal = [
            p
            for p in installed
            if isinstance(p, dict) and p.get("type") == "temporal"
        ]
        if not temporal:
            print(
                "No Temporal provider installed. Connect Temporal under Providers first "
                "(provider-mock Temporal tab → Register Temporal).",
                file=sys.stderr,
            )
            return 1
        provider_id = temporal[0].get("id")
        print(
            f"Using Temporal provider: {provider_id} "
            f"({temporal[0].get('details', {}).get('name') or temporal[0].get('name')})"
        )

    payload = {
        "name": "Remediate NVIDIA GPU",
        "description": (
            "Call the provider-mock NVIDIA GPU server to remediate a node. "
            "On success, resolve the Keep incident; on failure, send a mock ops email."
        ),
        "workflow_type": "RemediateNvidiaGpu",
        "task_queue": "keep-ops",
        "provider_id": provider_id,
        "catalog_key": "remediate-nvidia-gpu",
        "input_mapping": {
            "incident_id": "id",
            "name": "name",
            "severity": "severity",
            "host": "enrichments.gpu_host",
        },
        "disabled": False,
    }

    status, existing = _request("GET", f"{api_url}/temporal-workflows", api_key)
    if status != 200:
        print(f"Failed to list catalog ({status}): {existing}", file=sys.stderr)
        return 1
    match = None
    if isinstance(existing, list):
        match = next(
            (e for e in existing if e.get("catalog_key") == payload["catalog_key"]),
            None,
        )

    if match:
        status, result = _request(
            "PUT",
            f"{api_url}/temporal-workflows/{match['id']}",
            api_key,
            payload,
        )
        action = "updated"
    else:
        status, result = _request(
            "POST", f"{api_url}/temporal-workflows", api_key, payload
        )
        action = "created"

    if status not in (200, 201):
        print(f"Failed to register catalog ({status}): {result}", file=sys.stderr)
        return 1

    print(f"Catalog entry {action}:")
    print(json.dumps(result, indent=2))
    print(
        "\nFire GPU alerts from provider-mock (GPU: rule + temp/mem), or start "
        "Remediate NVIDIA GPU from an incident Workflows tab."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
