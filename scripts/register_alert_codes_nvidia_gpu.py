#!/usr/bin/env python3
"""Register DCGM exporter + diagnostics alert codes in Keep's alert catalog.

Usage:

  python scripts/register_alert_codes_nvidia_gpu.py

Env:
  KEEP_API_URL=http://localhost:8080
  KEEP_API_KEY=keepappkey
  KEEP_WORKFLOW_ID=mock-nvidia-gpu-remediate
  KEEP_AUTO_RUN_ON=both
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

from app.setup_actions import register_nvidia_gpu_alert_codes  # noqa: E402


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
    workflow_id = os.environ.get("KEEP_WORKFLOW_ID", "mock-nvidia-gpu-remediate")
    demo_auto_run = os.environ.get("KEEP_AUTO_RUN_ON", "both")

    def request_fn(method: str, path: str, body: dict | None = None) -> tuple[int, object]:
        return _request(method, f"{api_url}{path}", api_key, body)

    try:
        result = register_nvidia_gpu_alert_codes(
            request_fn,
            workflow_id=workflow_id,
            auto_run_on=demo_auto_run,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(
        f"Alert catalog (DCGM): created={result['created']} "
        f"updated={result['updated']} skipped={result['skipped']} "
        f"total={result['total']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
