"""Temporal workflows for Keep ops demos."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from app.activities import create_zip_from_ls, run_ls


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
