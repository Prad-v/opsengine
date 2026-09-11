"""Temporal workflows for synthetic checks."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.activities import notify_keep_alert, probe_target

MAX_PARALLEL = 10
PROBE_TIMEOUT = timedelta(seconds=60)
ALERT_TIMEOUT = timedelta(seconds=30)
RETRY = RetryPolicy(maximum_attempts=2)


def _normalize_group_input(input_data: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(input_data or {})
    targets = payload.get("targets") or []
    if isinstance(targets, str):
        targets = [line.strip() for line in targets.splitlines() if line.strip()]
    payload["targets"] = [str(t).strip() for t in targets if str(t).strip()]
    payload["prober"] = str(payload.get("prober") or "http").lower()
    payload["module_config"] = payload.get("module_config") or {}
    payload["labels"] = payload.get("labels") or {}
    payload["check_key"] = payload.get("check_key") or "manual"
    payload["name"] = payload.get("name") or payload["check_key"]
    return payload


async def _probe_and_alert(
    *,
    target: str,
    prober: str,
    module_config: dict[str, Any],
    check_key: str,
    check_name: str,
    labels: dict[str, Any],
) -> dict[str, Any]:
    result = await workflow.execute_activity(
        probe_target,
        {
            "target": target,
            "prober": prober,
            "module_config": module_config,
            "check_key": check_key,
            "labels": labels,
        },
        start_to_close_timeout=PROBE_TIMEOUT,
        retry_policy=RETRY,
    )
    alert = await workflow.execute_activity(
        notify_keep_alert,
        {
            "result": result,
            "check_key": check_key,
            "check_name": check_name,
            "labels": labels,
        },
        start_to_close_timeout=ALERT_TIMEOUT,
        retry_policy=RETRY,
    )
    return {"result": result, "alert": alert}


async def _run_targets(payload: dict[str, Any]) -> dict[str, Any]:
    targets: list[str] = payload["targets"]
    results: list[dict[str, Any]] = []
    successes = 0
    failures = 0

    for i in range(0, len(targets), MAX_PARALLEL):
        batch = targets[i : i + MAX_PARALLEL]
        batch_results = await asyncio.gather(
            *[
                _probe_and_alert(
                    target=target,
                    prober=payload["prober"],
                    module_config=payload["module_config"],
                    check_key=str(payload["check_key"]),
                    check_name=str(payload["name"]),
                    labels=payload["labels"],
                )
                for target in batch
            ]
        )
        for item in batch_results:
            results.append(item)
            if item.get("result", {}).get("success"):
                successes += 1
            else:
                failures += 1

    return {
        "check_id": payload.get("check_id"),
        "check_key": payload.get("check_key"),
        "prober": payload.get("prober"),
        "successes": successes,
        "failures": failures,
        "results": results,
    }


@workflow.defn(name="ProbeTarget")
class ProbeTarget:
    """Probe a single target (Mode 1/2 building block)."""

    @workflow.run
    async def run(self, input_data: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = _normalize_group_input(input_data)
        target = payload.get("target") or (
            payload["targets"][0] if payload["targets"] else ""
        )
        if not target:
            raise ValueError("target is required")
        item = await _probe_and_alert(
            target=target,
            prober=payload["prober"],
            module_config=payload["module_config"],
            check_key=str(payload["check_key"]),
            check_name=str(payload["name"]),
            labels=payload["labels"],
        )
        return item


@workflow.defn(name="ProbeTargetGroup")
class ProbeTargetGroup:
    """Mode 1: Temporal Schedule / Run-now for a configured check group."""

    @workflow.run
    async def run(self, input_data: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = _normalize_group_input(input_data)
        if not payload["targets"]:
            raise ValueError("targets list is empty")
        return await _run_targets(payload)


@workflow.defn(name="ProbeTargets")
class ProbeTargets:
    """Mode 2: on-demand probe of an explicit target list."""

    @workflow.run
    async def run(self, input_data: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = _normalize_group_input(input_data)
        if not payload["targets"]:
            # Allow Mode 2 to pass targets via enrichment-style string key.
            raw = payload.get("targets_csv") or payload.get("target_list")
            if isinstance(raw, str):
                payload["targets"] = [
                    part.strip() for part in raw.replace("\n", ",").split(",") if part.strip()
                ]
        if not payload["targets"]:
            raise ValueError("targets list is empty")
        return await _run_targets(payload)
