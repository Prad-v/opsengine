"""Temporal activities for synthetic probes, metrics, and Keep alerts."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx
from temporalio import activity

from app.otel_setup import record_probe_metrics
from app.probers.dns import probe_dns
from app.probers.http import probe_http
from app.probers.tcp import probe_tcp

logger = logging.getLogger(__name__)

PROBERS = {
    "http": probe_http,
    "tcp": probe_tcp,
    "dns": probe_dns,
}


@activity.defn
def probe_target(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Probe a single target.

    payload:
      - target: str
      - prober: http|tcp|dns
      - module_config: dict
      - check_key: optional
      - labels: optional dict
    """
    target = str(payload.get("target") or "").strip()
    prober = str(payload.get("prober") or "http").lower()
    module_config = payload.get("module_config") or {}
    check_key = payload.get("check_key")
    labels = payload.get("labels") or {}

    if not target:
        raise ValueError("target is required")
    if prober not in PROBERS:
        raise ValueError(f"Unsupported prober: {prober}")

    result = PROBERS[prober](target, module_config)
    result["check_key"] = check_key
    result["labels"] = labels
    result["probed_at"] = datetime.now(tz=timezone.utc).isoformat()

    record_probe_metrics(
        success=bool(result.get("success")),
        duration_seconds=float(result.get("duration_seconds") or 0),
        target=target,
        prober=prober,
        check_key=str(check_key) if check_key else None,
        labels=labels if isinstance(labels, dict) else None,
    )
    return result


@activity.defn
def notify_keep_alert(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Post firing/resolved AlertDto to Keep.

    payload:
      - result: probe result dict
      - check_key, check_name, labels
    """
    api_url = os.environ.get("KEEP_API_URL", "").rstrip("/")
    api_key = os.environ.get("KEEP_API_KEY", "")
    if not api_url or not api_key:
        logger.warning("KEEP_API_URL/KEEP_API_KEY not set; skipping Keep alert")
        return {"skipped": True, "reason": "missing_keep_config"}

    result = payload.get("result") or {}
    check_key = str(payload.get("check_key") or result.get("check_key") or "manual")
    check_name = str(payload.get("check_name") or check_key)
    prober = str(result.get("prober") or "http")
    target = str(result.get("target") or "")
    success = bool(result.get("success"))
    labels = dict(payload.get("labels") or result.get("labels") or {})
    labels.update(
        {
            "module": prober,
            "prober": prober,
            "check_key": check_key,
            "target": target,
        }
    )

    fingerprint = f"synth:{check_key}:{prober}:{target}"
    status = "resolved" if success else "firing"
    severity = "info" if success else str(payload.get("severity") or "warning")
    duration = result.get("duration_seconds")
    error = result.get("error")
    description = (
        f"probe_success={1 if success else 0} "
        f"latency={duration}s"
        + (f" error={error}" if error else "")
    )

    alert = {
        "name": f"Synthetic check {'passed' if success else 'failed'}: {target}",
        "status": status,
        "severity": severity,
        "source": ["synthetic-checks"],
        "fingerprint": fingerprint,
        "service": labels.get("service") or check_key,
        "url": target if prober == "http" else None,
        "description": description,
        "message": f"{check_name} ({prober}) against {target}",
        "labels": labels,
        "lastReceived": datetime.now(tz=timezone.utc).isoformat(),
    }

    try:
        response = httpx.post(
            f"{api_url}/alerts/event",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json=alert,
            timeout=15.0,
        )
        response.raise_for_status()
        return {
            "posted": True,
            "status_code": response.status_code,
            "fingerprint": fingerprint,
            "alert_status": status,
        }
    except Exception as exc:
        logger.exception("Failed to post Keep alert")
        return {"posted": False, "error": str(exc), "fingerprint": fingerprint}
