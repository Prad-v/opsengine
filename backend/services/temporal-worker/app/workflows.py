"""Temporal workflows for Keep ops demos."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from app.activities import (
        create_zip_from_ls,
        remediate_nvidia_gpu,
        request_keep_approval,
        resolve_keep_incident,
        run_ls,
        send_gpu_failure_email,
    )


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
    Remediate a mock NVIDIA GPU node, then close the Keep incident or email on failure.

    Input (dict):
      - incident_id: Keep incident id (required for resolve / email)
      - host: GPU node hostname (default gpu-node-a03)
      - action: remediation action (default reset_gpu)
      - gpu_index: GPU index (default 0)
      - wait_for_approval: if true, create a Keep approval request and wait
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
        wait_for_approval = bool(payload.get("wait_for_approval"))

        if wait_for_approval:
            info = workflow.info()
            await workflow.execute_activity(
                request_keep_approval,
                {
                    "title": f"Remediate GPU {host} ({action})",
                    "summary": f"Temporal RemediateNvidiaGpu waiting for approval on {host}",
                    "workflow_id": info.workflow_id,
                    "run_id": info.run_id,
                    "incident_id": incident_id,
                    "host": host,
                    "action": action,
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
                }
            if not (self.decision or {}).get("approved", False):
                return {
                    "ok": False,
                    "reason": "approval_rejected",
                    "decision": self.decision,
                    "incident_id": incident_id,
                    "host": host,
                }

        rem_result = await workflow.execute_activity(
            remediate_nvidia_gpu,
            {
                "incident_id": incident_id,
                "action": action,
                "gpu_index": int(payload.get("gpu_index") or 0),
                "alertname": payload.get("alertname") or payload.get("name"),
                "name": payload.get("name"),
                "host": host,
            },
            start_to_close_timeout=timedelta(seconds=60),
        )

        if rem_result.get("ok"):
            resolve_result = await workflow.execute_activity(
                resolve_keep_incident,
                {
                    "incident_id": incident_id,
                    "comment": (
                        f"Auto-resolved after Temporal remediated {host} "
                        f"({action}): {rem_result.get('message')}"
                    ),
                },
                start_to_close_timeout=timedelta(seconds=30),
            )
            return {
                "ok": True,
                "incident_id": incident_id,
                "host": host,
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
            "remediation": rem_result,
            "email": email_result,
        }
