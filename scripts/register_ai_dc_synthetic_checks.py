#!/usr/bin/env python3
"""
Upsert AI-datacenter synthetic checks (NVIDIA + AMD inference/training) into Keep.

Targets the provider-mock probe endpoints so keep-synth can run without GPUs.
Default base URL is host.docker.internal:8099 (reachable from the Temporal worker).

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

from app.synth_probes import (  # noqa: E402
    SYNTH_ALERT_CODES,
    build_keep_synthetic_checks,
)


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


def _pick_temporal_provider(api_url: str, api_key: str, preferred: str | None) -> str | None:
    if preferred:
        return preferred
    status, providers = _request("GET", f"{api_url}/providers", api_key)
    if status != 200:
        print(f"Failed to list providers ({status}): {providers}", file=sys.stderr)
        return None
    installed = []
    if isinstance(providers, dict):
        installed = providers.get("installed_providers") or providers.get("providers") or []
    elif isinstance(providers, list):
        installed = providers
    temporal = [
        p for p in installed if isinstance(p, dict) and p.get("type") == "temporal"
    ]
    if not temporal:
        print(
            "No Temporal provider installed. Connect Temporal under Providers first.",
            file=sys.stderr,
        )
        return None
    provider_id = temporal[0].get("id")
    print(f"Using Temporal provider: {provider_id}")
    return provider_id


def _register_alert_codes(api_url: str, api_key: str) -> None:
    status, listed = _request("GET", f"{api_url}/alert-catalog", api_key)
    existing: set[str] = set()
    if status == 200 and isinstance(listed, list):
        existing = {
            item.get("code") for item in listed if isinstance(item, dict) and item.get("code")
        }
    elif status != 200:
        print(f"Alert catalog list failed ({status}); skipping SYNTH_* codes.", file=sys.stderr)
        return

    created = 0
    skipped = 0
    for item in SYNTH_ALERT_CODES:
        if item["code"] in existing:
            skipped += 1
            continue
        code, body = _request("POST", f"{api_url}/alert-catalog", api_key, {**item, "disabled": False})
        if code in (200, 201):
            created += 1
        elif code == 409:
            skipped += 1
        else:
            print(f"    failed {item['code']} ({code}): {body}", file=sys.stderr)
    print(f"Alert catalog SYNTH_*: created={created} skipped={skipped}")


def main() -> int:
    api_url = os.environ.get("KEEP_API_URL", "http://localhost:8080").rstrip("/")
    api_key = os.environ.get("KEEP_API_KEY", "keepappkey")
    base_url = os.environ.get(
        "SYNTH_TARGET_BASE_URL", "http://host.docker.internal:8099"
    ).rstrip("/")
    provider_id = _pick_temporal_provider(
        api_url, api_key, os.environ.get("TEMPORAL_PROVIDER_ID")
    )
    if not provider_id:
        return 1

    _register_alert_codes(api_url, api_key)

    status, existing = _request("GET", f"{api_url}/synthetic-checks", api_key)
    if status != 200:
        print(f"Failed to list synthetic checks ({status}): {existing}", file=sys.stderr)
        return 1
    by_key: dict[str, dict] = {}
    if isinstance(existing, list):
        by_key = {
            item.get("check_key"): item
            for item in existing
            if isinstance(item, dict) and item.get("check_key")
        }

    created = 0
    updated = 0
    failed = 0
    for payload in build_keep_synthetic_checks(base_url, provider_id):
        key = payload["check_key"]
        match = by_key.get(key)
        if match:
            code, body = _request(
                "PUT",
                f"{api_url}/synthetic-checks/{match['id']}",
                api_key,
                payload,
            )
            action = "updated"
        else:
            code, body = _request("POST", f"{api_url}/synthetic-checks", api_key, payload)
            action = "created"
        if code not in (200, 201):
            print(f"    failed {key} ({code}): {body}", file=sys.stderr)
            failed += 1
            continue
        if action == "created":
            created += 1
        else:
            updated += 1
        print(f"    {action} {key}")

    print(
        f"AI DC synthetic checks: created={created} updated={updated} failed={failed} "
        f"base={base_url}"
    )
    print("UI: Catalog → Synthetic checks   Fail a probe: mock UI → Synthetic checks tab")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
