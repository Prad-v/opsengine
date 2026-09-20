#!/usr/bin/env python3
"""Create Keep Service Topology for the NVIDIA GPU datacenter inventory.

Hierarchy: region → datacenter → row → rack → host → GPU (+ gpu-inference).

Usage:

  python scripts/register_nvidia_gpu_topology.py

Env:
  KEEP_API_URL=http://localhost:8080
  KEEP_API_KEY=keepappkey
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOCK_APP = ROOT / "backend" / "services" / "provider-mock"
if str(MOCK_APP) not in sys.path:
    sys.path.insert(0, str(MOCK_APP))

from app.gpu_topology import apply_keep_topology  # noqa: E402


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

    def request_fn(method: str, path: str, body: dict | None = None) -> tuple[int, object]:
        if "?" in path:
            route, query = path.split("?", 1)
            url = f"{api_url}{route}?{query}"
        else:
            url = f"{api_url}{path}"
        return _request(method, url, api_key, body)

    try:
        result = apply_keep_topology(request_fn)
    except RuntimeError as exc:
        print(f"Failed to register NVIDIA GPU topology: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    created = result.get("services_created") or []
    print(
        f"NVIDIA GPU topology: created {len(created)} services, "
        f"{result.get('dependencies_created', 0)} edges, "
        f"application_created={result.get('application_created')}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
