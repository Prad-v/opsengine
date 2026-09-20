#!/usr/bin/env python3
"""Register reserved NVIDIA GPU alert codes in Keep's alert catalog.

Usage:

  python scripts/register_alert_codes_nvidia_gpu.py

Env:
  KEEP_API_URL=http://localhost:8080
  KEEP_API_KEY=keepappkey
  KEEP_WORKFLOW_ID=mock-nvidia-gpu-remediate
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

CODES = (
    {
        "code": "NVIDIA_GPU_THERMAL",
        "name": "NVIDIA GPU thermal",
        "description": "DCGM GPU temperature exceeded threshold.",
    },
    {
        "code": "NVIDIA_GPU_MEMORY",
        "name": "NVIDIA GPU memory",
        "description": "GPU framebuffer utilization near capacity.",
    },
    {
        "code": "NVIDIA_GPU_XID",
        "name": "NVIDIA GPU XID",
        "description": "NVIDIA XID error reported by DCGM.",
    },
    {
        "code": "NVIDIA_GPU_ECC",
        "name": "NVIDIA GPU uncorrectable ECC",
        "description": "Uncorrectable ECC errors on HBM.",
    },
    {
        "code": "NVIDIA_GPU_THROTTLE",
        "name": "NVIDIA GPU thermal throttle",
        "description": "GPU clocks thermally throttled.",
    },
    {
        "code": "NVIDIA_GPU_NVLINK",
        "name": "NVIDIA NVLink error",
        "description": "NVLink CRC / flit errors on multi-GPU fabric.",
    },
    {
        "code": "NVIDIA_GPU_POWER",
        "name": "NVIDIA GPU power limit",
        "description": "GPU power draw at configured limit.",
    },
    {
        "code": "NVIDIA_GPU_UNAVAILABLE",
        "name": "NVIDIA GPU unavailable",
        "description": "GPU not ready — driver lost or device missing.",
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
    workflow_id = os.environ.get("KEEP_WORKFLOW_ID", "mock-nvidia-gpu-remediate")

    status, listed = _request("GET", f"{api_url}/alert-catalog", api_key)
    existing = {}
    if status == 200 and isinstance(listed, list):
        existing = {item.get("code"): item for item in listed if isinstance(item, dict)}
    elif status != 200:
        print(f"Failed to list alert catalog ({status}): {listed}", file=sys.stderr)
        return 1

    # Workflow may not exist yet — still register codes without auto-run.
    wf_status, _ = _request("GET", f"{api_url}/workflows/{workflow_id}", api_key)
    keep_workflow_id = workflow_id if wf_status == 200 else None
    auto_run_on = "both" if keep_workflow_id else "none"

    created = 0
    skipped = 0
    for item in CODES:
        if item["code"] in existing:
            print(f"    exists {item['code']}")
            skipped += 1
            continue
        payload = {
            **item,
            "keep_workflow_id": keep_workflow_id,
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
