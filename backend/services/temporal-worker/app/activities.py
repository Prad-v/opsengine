"""Activities for the Keep ops Temporal worker."""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from temporalio import activity


@activity.defn
def run_ls(path: str = ".") -> dict[str, Any]:
    """
    Run `ls -la` on the given path and return captured output.

    The path is resolved relative to TEMPORAL_WORKER_ROOT (default /data).
    """
    root = Path(os.environ.get("TEMPORAL_WORKER_ROOT", "/data")).resolve()
    target = (root / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()

    # Prevent escaping the worker root for relative paths.
    if not str(target).startswith(str(root)):
        raise ValueError(f"Path '{path}' is outside worker root '{root}'")
    if not target.exists():
        raise FileNotFoundError(f"Path does not exist: {target}")

    result = subprocess.run(
        ["ls", "-la", str(target)],
        check=False,
        capture_output=True,
        text=True,
    )
    return {
        "path": str(target),
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "listed_at": datetime.now(tz=timezone.utc).isoformat(),
    }


@activity.defn
def create_zip_from_ls(ls_result: dict[str, Any], incident_id: str | None = None) -> dict[str, Any]:
    """
    Write ls output into a zip archive under the worker output directory.

    Returns metadata including the zip file path (inside the container/volume).
    """
    root = Path(os.environ.get("TEMPORAL_WORKER_ROOT", "/data")).resolve()
    output_dir = root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = f"-{incident_id}" if incident_id else ""
    zip_name = f"ls-output{suffix}-{stamp}.zip"
    zip_path = output_dir / zip_name

    listing_name = "ls-output.txt"
    listing_body = (
        f"path: {ls_result.get('path')}\n"
        f"listed_at: {ls_result.get('listed_at')}\n"
        f"exit_code: {ls_result.get('exit_code')}\n\n"
        f"--- stdout ---\n{ls_result.get('stdout') or ''}\n"
        f"--- stderr ---\n{ls_result.get('stderr') or ''}\n"
    )

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(listing_name, listing_body)

    return {
        "zip_path": str(zip_path),
        "zip_name": zip_name,
        "bytes": zip_path.stat().st_size,
        "listing_file": listing_name,
        "incident_id": incident_id,
        "source_path": ls_result.get("path"),
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }


@activity.defn
def request_keep_approval(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Create a Keep approval request that will signal this Temporal workflow.

    Env:
      KEEP_API_URL (default http://host.docker.internal:8080)
      KEEP_API_KEY (default keepappkey)
    """
    base = os.environ.get("KEEP_API_URL", "http://host.docker.internal:8080").rstrip("/")
    api_key = os.environ.get("KEEP_API_KEY", "keepappkey")
    title = payload.get("title") or "Temporal workflow approval"
    body = {
        "action_type": "temporal_signal",
        "title": title,
        "summary": payload.get("summary"),
        "resource_type": "temporal_workflow",
        "resource_id": payload.get("workflow_id"),
        "payload": {
            "incident_id": payload.get("incident_id"),
            "host": payload.get("host"),
            "action": payload.get("action"),
            "temporal_workflow_id": payload.get("workflow_id"),
        },
        "context": {
            "host": payload.get("host"),
            "incident_id": payload.get("incident_id"),
        },
        "callback": {
            "kind": "temporal_signal",
            "workflow_id": payload.get("workflow_id"),
            "run_id": payload.get("run_id"),
            "signal_name": payload.get("signal_name") or "approve",
            "provider_id": payload.get("provider_id"),
        },
        "idempotency_key": payload.get("idempotency_key")
        or f"temporal:{payload.get('workflow_id')}:{payload.get('run_id')}",
    }
    status, result = _http_json(
        "POST",
        f"{base}/approvals",
        body=body,
        headers={"x-api-key": api_key},
    )
    return {
        "ok": status < 400,
        "http_status": status,
        "response": result,
        "keep_api_url": base,
    }


def _http_json(
    method: str,
    url: str,
    *,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> tuple[int, Any]:
    data = None
    req_headers = {"Accept": "application/json", **(headers or {})}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8") or "null"
            try:
                parsed: Any = json.loads(raw)
            except json.JSONDecodeError:
                parsed = raw
            return resp.status, parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw
        return exc.code, parsed


@activity.defn
def remediate_nvidia_gpu(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Call the provider-mock NVIDIA GPU server remediation endpoint.

    Env:
      GPU_MOCK_URL  (default http://host.docker.internal:8099)
    """
    base = os.environ.get("GPU_MOCK_URL", "http://host.docker.internal:8099").rstrip("/")
    url = f"{base}/gpu/server/remediate"
    body = {
        "action": payload.get("action") or "reset_gpu",
        "gpu_index": int(payload.get("gpu_index") or 0),
        "incident_id": payload.get("incident_id"),
        "alertname": payload.get("alertname") or payload.get("name"),
        "host": payload.get("host") or "gpu-node-a03",
    }
    status, result = _http_json("POST", url, body=body)
    # FastAPI HTTPException wraps the remediation entry under "detail".
    if isinstance(result, dict) and isinstance(result.get("detail"), dict):
        result = result["detail"]
    ok = status < 400 and isinstance(result, dict) and result.get("ok") is True
    if isinstance(result, dict):
        return {
            **result,
            "http_status": status,
            "ok": ok,
            "gpu_mock_url": url,
        }
    return {
        "ok": False,
        "http_status": status,
        "error": str(result),
        "gpu_mock_url": url,
    }


@activity.defn
def resolve_keep_incident(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Resolve a Keep incident via POST /incidents/{id}/status.

    Env:
      KEEP_API_URL (default http://host.docker.internal:8080)
      KEEP_API_KEY (default keepappkey)
    """
    incident_id = payload.get("incident_id")
    if not incident_id:
        raise ValueError("incident_id is required to resolve a Keep incident")
    base = os.environ.get("KEEP_API_URL", "http://host.docker.internal:8080").rstrip("/")
    api_key = os.environ.get("KEEP_API_KEY", "keepappkey")
    url = f"{base}/incidents/{incident_id}/status"
    comment = payload.get("comment") or "Resolved by Temporal RemediateNvidiaGpu"
    status, result = _http_json(
        "POST",
        url,
        body={"status": "resolved", "comment": comment},
        headers={"x-api-key": api_key},
    )
    return {
        "ok": status < 400,
        "http_status": status,
        "incident_id": str(incident_id),
        "response": result,
    }


@activity.defn
def send_gpu_failure_email(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Post a failure email into the provider-mock GPU email inbox.

    Env:
      GPU_MOCK_URL (default http://host.docker.internal:8099)
      GPU_ALERT_EMAIL_TO (default ops@ai-dc.local)
    """
    base = os.environ.get("GPU_MOCK_URL", "http://host.docker.internal:8099").rstrip("/")
    to_addr = (
        payload.get("to")
        or os.environ.get("GPU_ALERT_EMAIL_TO", "ops@ai-dc.local")
    )
    incident_id = payload.get("incident_id")
    host = payload.get("host") or "gpu-node-a03"
    error = payload.get("error") or "unknown remediation failure"
    subject = payload.get("subject") or f"[AI-DC] GPU remediation failed on {host}"
    body = payload.get("body") or (
        f"Temporal RemediateNvidiaGpu failed.\n\n"
        f"incident_id: {incident_id}\n"
        f"host: {host}\n"
        f"error: {error}\n"
        f"Please investigate the NVIDIA GPU node and re-run remediation.\n"
    )
    url = f"{base}/gpu/emails"
    status, result = _http_json(
        "POST",
        url,
        body={
            "to": to_addr,
            "subject": subject,
            "body": body,
            "incident_id": str(incident_id) if incident_id else None,
            "metadata": {
                "host": host,
                "action": payload.get("action") or "reset_gpu",
                "source": "temporal-RemediateNvidiaGpu",
            },
        },
    )
    return {
        "ok": status < 400,
        "http_status": status,
        "response": result,
        "to": to_addr,
        "subject": subject,
    }
