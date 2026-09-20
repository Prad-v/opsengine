#!/usr/bin/env python3
"""Register reserved payments mock alert codes in Keep's alert catalog.

Usage:

  python scripts/register_alert_codes_payments.py

Env:
  KEEP_API_URL=http://localhost:8080
  KEEP_API_KEY=keepappkey
  KEEP_WORKFLOW_ID=mock-grafana-list-and-zip
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

CODES = (
    {
        "code": "HIGH_CPU",
        "name": "High CPU",
        "description": "Host CPU above threshold on payments-api.",
    },
    {
        "code": "HIGH_MEMORY",
        "name": "High memory",
        "description": "Host memory above threshold on payments-api (Grafana or VictoriaMetrics).",
    },
    {
        "code": "DISK_SPACE_LOW",
        "name": "Disk space low",
        "description": "Disk space below threshold (Mimir Alertmanager mock).",
    },
)


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
    workflow_id = os.environ.get("KEEP_WORKFLOW_ID", "mock-grafana-list-and-zip")

    status, listed = _request("GET", f"{api_url}/alert-catalog", api_key)
    existing = {}
    if status == 200 and isinstance(listed, list):
        existing = {item.get("code"): item for item in listed if isinstance(item, dict)}
    elif status != 200:
        print(f"Failed to list alert catalog ({status}): {listed}", file=sys.stderr)
        return 1

    wf_status, _ = _request("GET", f"{api_url}/workflows/{workflow_id}", api_key)
    keep_workflow_id = workflow_id if wf_status == 200 else None

    created = 0
    skipped = 0
    for item in CODES:
        if item["code"] in existing:
            print(f"    exists {item['code']}")
            skipped += 1
            continue
        auto_run_on = "incident" if keep_workflow_id and item["code"] != "DISK_SPACE_LOW" else "none"
        linked = keep_workflow_id if auto_run_on != "none" else None
        if item["code"] == "DISK_SPACE_LOW":
            disk_status, _ = _request("GET", f"{api_url}/workflows/mock-mimir-disk", api_key)
            if disk_status == 200:
                linked = "mock-mimir-disk"
                auto_run_on = "both"
        payload = {
            **item,
            "keep_workflow_id": linked,
            "auto_run_on": auto_run_on,
            "disabled": False,
        }
        code, body = _request("POST", f"{api_url}/alert-catalog", api_key, payload)
        if code in (200, 201):
            print(f"    registered {item['code']}")
            created += 1
        elif code == 409:
            print(f"    exists {item['code']}")
            skipped += 1
        else:
            print(f"    failed {item['code']} ({code}): {body}", file=sys.stderr)
            return 1

    print(f"Alert catalog: created={created} skipped={skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
