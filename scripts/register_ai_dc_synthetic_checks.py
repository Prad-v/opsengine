#!/usr/bin/env python3
"""
Upsert AI-datacenter synthetic checks (NVIDIA + AMD inference/training) into Keep.

Usage:

  python scripts/register_ai_dc_synthetic_checks.py

Env:
  KEEP_API_URL=http://localhost:8080
  KEEP_API_KEY=keepappkey
  TEMPORAL_PROVIDER_ID=
  SYNTH_TARGET_BASE_URL=http://host.docker.internal:8099
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib import error, request

ROOT = Path(__file__).resolve().parents[1]
MOCK_APP = ROOT / "backend" / "services" / "provider-mock"
if str(MOCK_APP) not in sys.path:
    sys.path.insert(0, str(MOCK_APP))

from app.setup_actions import register_ai_dc_synthetic_checks  # noqa: E402


def _request(method: str, url: str, api_key: str, body: dict | None = None) -> tuple[int, object]:
    data = None
    headers = {"x-api-key": api_key, "Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8") or "null"
            return resp.status, json.loads(raw)
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw
        return exc.code, parsed


def main() -> int:
    api_url = os.environ.get("KEEP_API_URL", "http://localhost:8080").rstrip("/")
    api_key = os.environ.get("KEEP_API_KEY", "keepappkey")
    base_url = os.environ.get(
        "SYNTH_TARGET_BASE_URL", "http://host.docker.internal:8099"
    ).rstrip("/")

    def request_fn(method: str, path: str, body: dict | None = None) -> tuple[int, object]:
        return _request(method, f"{api_url}{path}", api_key, body)

    try:
        result = register_ai_dc_synthetic_checks(
            request_fn,
            provider_id=os.environ.get("TEMPORAL_PROVIDER_ID"),
            target_base_url=base_url,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    alert = result.get("alert_codes") or {}
    print(
        f"Alert catalog SYNTH_*: created={alert.get('created', 0)} "
        f"skipped={alert.get('skipped', 0)}"
    )
    print(
        f"AI DC synthetic checks: created={result['created']} "
        f"updated={result['updated']} failed={result['failed']} "
        f"base={result['base_url']}"
    )
    print("UI: Catalog → Synthetic checks   Fail a probe: mock UI → Synthetic checks tab")
    print("Or: mock UI → Setup → AI DC synthetic checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
