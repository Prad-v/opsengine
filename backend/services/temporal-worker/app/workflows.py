"""Temporal workflows for Keep ops demos."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from app.activities import (
        cordon_nvidia_gpu,
        create_zip_from_ls,
        remediate_nvidia_gpu,
        request_keep_approval,
        resolve_keep_incident,
        run_dcgm_diag,
        run_ls,
        send_gpu_failure_email,
        uncordon_nvidia_gpu,
    )


_SUITE_LEVEL = {
    "1": 1,
    "quick": 1,
    "short": 1,
    "2": 2,
    "medium": 2,
    "3": 3,
    "long": 3,
    "4": 4,
    "xlong": 4,
    "production_testing": 3,
}


def _suite_key(suite: Any, run: Any) -> str:
    raw = str(suite or run or "2").strip().lower().replace(" ", "_")
    return raw or "2"


def _suite_level(key: str) -> int:
    return _SUITE_LEVEL.get(key, 2)


@workflow.defn(name="ListAndZipDirectory")
class ListAndZipDirectory:
    """
    Run `ls` on a path, capture output, and package it into a zip file.

    Input (dict):
      - path: directory to list (relative to worker root, default "sample")
      - incident_id: optional Keep incident id for zip naming / tracing
    """

    @workflow.run
    async def run(self, input_data: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = input_data or {}
        path = str(payload.get("path") or "sample")
        if path in ("", "None", "null"):
            path = "sample"
        incident_id = payload.get("incident_id")
        if incident_id is not None:
            incident_id = str(incident_id)

        ls_result = await workflow.execute_activity(
            run_ls,
            path,
            start_to_close_timeout=timedelta(seconds=30),
        )
        zip_result = await workflow.execute_activity(
            create_zip_from_ls,
            args=[ls_result, incident_id],
            start_to_close_timeout=timedelta(seconds=60),
        )
        return {
            "incident_id": incident_id,
            "ls": ls_result,
            "zip": zip_result,
        }


@workflow.defn(name="RemediateNvidiaGpu")
class RemediateNvidiaGpu:
    """
    Cordon (L2+), approve (L3+), run DCGM diagnostics, then remediate or isolate.

    Input (dict):
      - incident_id: Keep incident id (required for resolve / email)
      - host: GPU node hostname (default gpu-node-a03)
      - action: post-Pass remediation action (default reset_gpu)
      - gpu_index: GPU index (default 0)
      - suite / run: dcgmi diag suite (1-4) or named plugins; optional
      - alert_code / code: reserved DCGM_* code for suite hints
      - skip_diag: if true, skip diagnostics and remediate directly
      - skip_cordon: if true, skip cordon/drain even for L2+
      - wait_for_approval: force approval; L3+ auto-requires unless skip_approval
      - skip_approval: allow unattended L3+ (escape hatch)
      - name / alertname: optional alert context
    """

    def __init__(self) -> None:
        self.decision: dict[str, Any] | None = None

    @workflow.signal
    def approve(self, payload: dict[str, Any] | None = None) -> None:
        self.decision = payload or {"approved": True}

    @workflow.run
    async def run(self, input_data: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = input_data or {}
        incident_id = payload.get("incident_id")
        if incident_id is not None:
            incident_id = str(incident_id)
        host = str(payload.get("host") or "gpu-node-a03")
        action = str(payload.get("action") or "reset_gpu")
        skip_diag = bool(payload.get("skip_diag"))
        skip_cordon = bool(payload.get("skip_cordon"))
        skip_approval = bool(payload.get("skip_approval"))
        gpu_index = int(payload.get("gpu_index") or 0)
        alertname = payload.get("alertname") or payload.get("name")
        suite_key = _suite_key(payload.get("suite") or payload.get("run"), payload.get("run"))
        level = _suite_level(suite_key)
        wait_for_approval = bool(payload.get("wait_for_approval")) or (
            level >= 3 and not skip_approval
        )
        need_cordon = not skip_diag and not skip_cordon and level >= 2

        cordon_result: dict[str, Any] | None = None
        uncordon_result: dict[str, Any] | None = None

        if wait_for_approval:
            info = workflow.info()
            await workflow.execute_activity(
                request_keep_approval,
                {
                    "title": (
                        f"DCGM diag suite={suite_key} (L{level}) on {host}"
                    ),
                    "summary": (
                        f"Temporal RemediateNvidiaGpu awaiting approval for "
                        f"suite={suite_key} level={level} on {host}"
                    ),
                    "workflow_id": info.workflow_id,
                    "run_id": info.run_id,
                    "incident_id": incident_id,
                    "host": host,
                    "action": f"dcgm_diag:{suite_key}",
                    "signal_name": "approve",
                },
                start_to_close_timeout=timedelta(seconds=30),
            )
            try:
                await workflow.wait_condition(
                    lambda: self.decision is not None,
                    timeout=timedelta(hours=24),
                )
            except TimeoutError:
                return {
                    "ok": False,
                    "reason": "approval_timeout",
                    "incident_id": incident_id,
                    "host": host,
                    "suite": suite_key,
                    "suite_level": level,
                }
            if not (self.decision or {}).get("approved", False):
                return {
                    "ok": False,
                    "reason": "approval_rejected",
                    "decision": self.decision,
                    "incident_id": incident_id,
                    "host": host,
                    "suite": suite_key,
                    "suite_level": level,
                }

        if need_cordon:
            cordon_result = await workflow.execute_activity(
                cordon_nvidia_gpu,
                {
                    "host": host,
                    "drain": True,
                    "incident_id": incident_id,
                    "reason": f"dcgm_diag_suite_{suite_key}",
                },
                start_to_close_timeout=timedelta(seconds=30),
            )
            if not cordon_result.get("ok"):
                email_result = await workflow.execute_activity(
                    send_gpu_failure_email,
                    {
                        "incident_id": incident_id,
                        "host": host,
                        "action": "cordon",
                        "error": cordon_result.get("error") or "cordon failed",
                        "subject": f"[AI-DC] GPU cordon failed on {host}",
                    },
                    start_to_close_timeout=timedelta(seconds=30),
                )
                return {
                    "ok": False,
                    "reason": "cordon_failed",
                    "incident_id": incident_id,
                    "host": host,
                    "suite": suite_key,
                    "suite_level": level,
                    "cordon": cordon_result,
                    "email": email_result,
                }

        diag_result: dict[str, Any] | None = None
        recommendation = "RESET"
        if not skip_diag:
            # L3/L4 can run 15+ minutes on real hardware; mock is fast.
            diag_timeout = timedelta(minutes=30) if level >= 3 else timedelta(seconds=120)
            diag_result = await workflow.execute_activity(
                run_dcgm_diag,
                {
                    "incident_id": incident_id,
                    "host": host,
                    "gpu_index": gpu_index,
                    "suite": suite_key,
                    "run": payload.get("run"),
                    "alert_code": payload.get("alert_code") or payload.get("code"),
                    "alertname": alertname,
                    "name": payload.get("name"),
                    "mode": payload.get("mode"),
                },
                start_to_close_timeout=diag_timeout,
            )
            if not diag_result.get("ok"):
                email_result = await workflow.execute_activity(
                    send_gpu_failure_email,
                    {
                        "incident_id": incident_id,
                        "host": host,
                        "action": "dcgm_diag",
                        "error": (
                            diag_result.get("error")
                            or diag_result.get("message")
                            or "dcgm diag transport failed"
                        ),
                        "subject": f"[AI-DC] DCGM diag failed to run on {host}",
                    },
                    start_to_close_timeout=timedelta(seconds=30),
                )
                return {
                    "ok": False,
                    "reason": "diag_transport_failed",
                    "incident_id": incident_id,
                    "host": host,
                    "suite": suite_key,
                    "suite_level": level,
                    "recommendation": "ISOLATE",
                    "cordon": cordon_result,
                    "diag": diag_result,
                    "email": email_result,
                }

            recommendation = str(diag_result.get("recommendation") or "ISOLATE").upper()
            if recommendation == "ISOLATE" or not diag_result.get("diag_pass"):
                email_result = await workflow.execute_activity(
                    send_gpu_failure_email,
                    {
                        "incident_id": incident_id,
                        "host": host,
                        "action": "isolate_gpu",
                        "error": (
                            diag_result.get("message")
                            or diag_result.get("error_code")
                            or "DCGM diag Fail — isolate GPU"
                        ),
                        "subject": (
                            f"[AI-DC] DCGM diag ISOLATE on {host} "
                            f"({diag_result.get('error_code') or 'Fail'})"
                        ),
                        "body": (
                            f"Temporal RemediateNvidiaGpu isolation path.\n\n"
                            f"incident_id: {incident_id}\n"
                            f"host: {host}\n"
                            f"suite: {diag_result.get('suite')}\n"
                            f"result: {diag_result.get('result')}\n"
                            f"error_code: {diag_result.get('error_code')}\n"
                            f"severity: {diag_result.get('severity')}\n"
                            f"message: {diag_result.get('message')}\n\n"
                            f"Node left cordoned. Do not auto-reset.\n"
                        ),
                    },
                    start_to_close_timeout=timedelta(seconds=30),
                )
                return {
                    "ok": False,
                    "reason": "diag_isolate",
                    "incident_id": incident_id,
                    "host": host,
                    "suite": suite_key,
                    "suite_level": level,
                    "recommendation": "ISOLATE",
                    "cordon": cordon_result,
                    "diag": diag_result,
                    "email": email_result,
                }

        rem_result = await workflow.execute_activity(
            remediate_nvidia_gpu,
            {
                "incident_id": incident_id,
                "action": action,
                "gpu_index": gpu_index,
                "alertname": alertname,
                "name": payload.get("name"),
                "host": host,
            },
            start_to_close_timeout=timedelta(seconds=60),
        )

        if rem_result.get("ok"):
            if need_cordon:
                uncordon_result = await workflow.execute_activity(
                    uncordon_nvidia_gpu,
                    {
                        "host": host,
                        "incident_id": incident_id,
                        "reason": "remediation_ok",
                    },
                    start_to_close_timeout=timedelta(seconds=30),
                )
            resolve_result = await workflow.execute_activity(
                resolve_keep_incident,
                {
                    "incident_id": incident_id,
                    "comment": (
                        f"Auto-resolved after DCGM diag Pass + Temporal remediated "
                        f"{host} ({action}): {rem_result.get('message')}"
                    ),
                },
                start_to_close_timeout=timedelta(seconds=30),
            )
            return {
                "ok": True,
                "incident_id": incident_id,
                "host": host,
                "suite": suite_key,
                "suite_level": level,
                "recommendation": recommendation,
                "cordon": cordon_result,
                "uncordon": uncordon_result,
                "diag": diag_result,
                "remediation": rem_result,
                "resolve": resolve_result,
            }

        email_result = await workflow.execute_activity(
            send_gpu_failure_email,
            {
                "incident_id": incident_id,
                "host": host,
                "action": action,
                "error": rem_result.get("error") or rem_result.get("message") or "remediation failed",
            },
            start_to_close_timeout=timedelta(seconds=30),
        )
        return {
            "ok": False,
            "incident_id": incident_id,
            "host": host,
            "suite": suite_key,
            "suite_level": level,
            "recommendation": recommendation,
            "cordon": cordon_result,
            "diag": diag_result,
            "remediation": rem_result,
            "email": email_result,
        }
