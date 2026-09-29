#!/usr/bin/env python3
"""
Register the ProbeTargets Temporal workflow in Keep's catalog (Mode 2).

Usage:

  python scripts/register_temporal_probe_targets_catalog.py

Env:
  KEEP_API_URL=http://localhost:8080
  KEEP_API_KEY=keepappkey
  TEMPORAL_PROVIDER_ID=
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

from app.setup_actions import register_probe_targets_catalog  # noqa: E402


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
        return _request(method, f"{api_url}{path}", api_key, body)

    try:
        result = register_probe_targets_catalog(
            request_fn, provider_id=os.environ.get("TEMPORAL_PROVIDER_ID")
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Catalog entry {result['action']}:")
    print(json.dumps(result.get("entry"), indent=2))
    print(
        "\nStart from an incident Workflows tab. Set enrichments:\n"
        "  synth_prober=http\n"
        "  synth_targets=[\"https://example.com\"]  (JSON list) or use Mode 1 UI checks.\n"
        "Ensure: make synthetic-checks"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
