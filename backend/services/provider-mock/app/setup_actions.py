"""Keep catalog / demo setup actions used by provider-mock UI and Makefile scripts.

Each action talks to Keep through a request callable::

    request_fn(method, path, body=None) -> (status_code, body)
    upload_fn(path, filename, content, content_type) -> (status_code, body)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from app.alert_codes_nvidia import CODES as NVIDIA_GPU_CODES, DEMO_AUTO_RUN_CODES
from app.alert_codes_payments import PAYMENTS_ALERT_CODES
from app.gpu_topology import apply_keep_topology
from app.synth_probes import PROBE_SPECS, SYNTH_ALERT_CODES, build_keep_synthetic_checks

RequestFn = Callable[[str, str, dict[str, Any] | None], tuple[int, Any]]
UploadFn = Callable[[str, str, bytes, str], tuple[int, Any]]

DEMO_WORKFLOWS_DIR = Path(__file__).parent / "demo_workflows"

LIST_AND_ZIP_CATALOG = {
    "name": "List and Zip Directory",
    "description": (
        "Run ls on a path inside the Temporal worker, capture stdout, "
        "and package the listing into a zip under /data/output."
    ),
    "workflow_type": "ListAndZipDirectory",
    "task_queue": "keep-ops",
    "catalog_key": "list-and-zip-directory",
    "input_mapping": {
        "incident_id": "id",
        "path": "enrichments.list_path",
        "name": "name",
        "severity": "severity",
    },
    "disabled": False,
}

NVIDIA_GPU_CATALOG = {
    "name": "Remediate NVIDIA GPU",
    "description": (
        "Cordon (L2+), approve (L3+), run DCGM diagnostics on the "
        "provider-mock GPU server, then reset+uncordon on Pass/RESET or "
        "email ops and leave cordoned on Fail/ISOLATE."
    ),
    "workflow_type": "RemediateNvidiaGpu",
    "task_queue": "keep-ops",
    "catalog_key": "remediate-nvidia-gpu",
    "input_mapping": {
        "incident_id": "id",
        "name": "name",
        "severity": "severity",
        "host": "enrichments.gpu_host",
        "suite": "enrichments.gpu_diag_suite",
        "alert_code": "code",
    },
    "disabled": False,
}

PROBE_TARGETS_CATALOG = {
    "name": "Probe Targets",
    "description": (
        "On-demand synthetic checks (HTTP/TCP/DNS) against a list of targets "
        "on the keep-synth worker. Pass targets via incident enrichments."
    ),
    "workflow_type": "ProbeTargets",
    "task_queue": "keep-synth",
    "catalog_key": "probe-targets",
    "input_mapping": {
        "incident_id": "id",
        "name": "name",
        "prober": "enrichments.synth_prober",
        "targets": "enrichments.synth_targets",
        "check_key": "enrichments.synth_check_key",
    },
    "disabled": False,
}


def list_setup_actions() -> list[dict[str, Any]]:
    """UI catalog of Keep setup actions (mirrors Makefile) with selectable items."""
    temporal_items = [
        {
            "id": item["catalog_key"],
            "label": item["name"],
            "description": item["description"],
            "meta": item["workflow_type"],
        }
        for item in (LIST_AND_ZIP_CATALOG, NVIDIA_GPU_CATALOG, PROBE_TARGETS_CATALOG)
    ]
    payments_items = [
        {
            "id": item["code"],
            "label": item["name"],
            "description": item["description"],
            "meta": item["code"],
        }
        for item in PAYMENTS_ALERT_CODES
    ]
    nvidia_items = [
        {
            "id": item["code"],
            "label": item["name"],
            "description": item["description"],
            "meta": item["code"],
            "tags": list(item.get("tags") or []),
            "recommended": item["code"] in DEMO_AUTO_RUN_CODES,
        }
        for item in NVIDIA_GPU_CODES
    ]
    synth_items = [
        {
            "id": spec["id"],
            "label": spec["name"],
            "description": spec["description"],
            "meta": spec.get("code") or spec["id"],
            "tags": [spec.get("group") or "synth"],
            "alert_code": spec.get("code"),
        }
        for spec in PROBE_SPECS
    ]
    workflow_items = [
        {
            "id": path.name,
            "label": path.stem,
            "description": f"Upload Keep workflow {path.name}",
            "meta": path.name,
        }
        for path in sorted(DEMO_WORKFLOWS_DIR.glob("*.yml"))
    ]

    return [
        {
            "id": "list-and-zip-catalog",
            "group": "temporal-catalog",
            "title": "ListAndZipDirectory catalog",
            "description": "Register Temporal keep-ops ListAndZipDirectory (make register-list-and-zip-catalog).",
            "makefile": "register-list-and-zip-catalog",
            "selectable": True,
            "item_key": "items",
            "items": [temporal_items[0]],
        },
        {
            "id": "nvidia-gpu-catalog",
            "group": "temporal-catalog",
            "title": "RemediateNvidiaGpu catalog",
            "description": "Register Temporal keep-ops RemediateNvidiaGpu (make register-nvidia-gpu-catalog).",
            "makefile": "register-nvidia-gpu-catalog",
            "selectable": True,
            "item_key": "items",
            "items": [temporal_items[1]],
        },
        {
            "id": "probe-targets-catalog",
            "group": "temporal-catalog",
            "title": "ProbeTargets catalog",
            "description": "Register Temporal keep-synth ProbeTargets (make register-probe-targets-catalog).",
            "makefile": "register-probe-targets-catalog",
            "selectable": True,
            "item_key": "items",
            "items": [temporal_items[2]],
        },
        {
            "id": "payments-alert-codes",
            "group": "alert-codes",
            "title": "Payments alert codes",
            "description": "Register HIGH_CPU / HIGH_MEMORY / DISK_SPACE_LOW (make register-payments-alert-codes).",
            "makefile": "register-payments-alert-codes",
            "selectable": True,
            "item_key": "items",
            "items": payments_items,
        },
        {
            "id": "nvidia-gpu-alert-codes",
            "group": "alert-codes",
            "title": "NVIDIA GPU alert codes",
            "description": "Register DCGM_* reserved codes (make register-nvidia-gpu-alert-codes). Select individual codes or all.",
            "makefile": "register-nvidia-gpu-alert-codes",
            "selectable": True,
            "item_key": "items",
            "items": nvidia_items,
        },
        {
            "id": "nvidia-gpu-topology",
            "group": "topology",
            "title": "NVIDIA GPU topology",
            "description": "Seed region/datacenter/row/rack/GPU Service Topology (make register-nvidia-gpu-topology).",
            "makefile": "register-nvidia-gpu-topology",
            "selectable": False,
            "item_key": "items",
            "items": [],
        },
        {
            "id": "ai-dc-synthetic-checks",
            "group": "synthetics",
            "title": "AI DC synthetic checks",
            "description": "Seed NVIDIA/AMD inference+training synthetics (make register-ai-dc-synthetic-checks).",
            "makefile": "register-ai-dc-synthetic-checks",
            "selectable": True,
            "item_key": "items",
            "items": synth_items,
        },
        {
            "id": "demo-workflows",
            "group": "workflows",
            "title": "Demo Keep workflows",
            "description": "Upload individual mock workflow YAML files into Keep.",
            "makefile": "demo-list-and-zip / demo-nvidia-gpu",
            "selectable": True,
            "item_key": "items",
            "items": workflow_items,
        },
        {
            "id": "demo-list-and-zip",
            "group": "demos",
            "title": "Demo: Grafana → ListAndZip",
            "description": "Catalog + payments codes + mock workflows (make demo-list-and-zip).",
            "makefile": "demo-list-and-zip",
            "selectable": False,
            "item_key": "items",
            "items": [],
        },
        {
            "id": "demo-nvidia-gpu",
            "group": "demos",
            "title": "Demo: NVIDIA GPU remediate",
            "description": "Full GPU remediate setup (make demo-nvidia-gpu / make start).",
            "makefile": "demo-nvidia-gpu",
            "selectable": False,
            "item_key": "items",
            "items": [],
        },
    ]


def _filter_by_ids(
    rows: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    id_field: str,
    selected: list[str] | None,
) -> list[dict[str, Any]]:
    if not selected:
        return list(rows)
    wanted = {str(x) for x in selected}
    filtered = [row for row in rows if str(row.get(id_field)) in wanted]
    if not filtered:
        raise RuntimeError(
            f"No matching items for {sorted(wanted)}. "
            f"Known sample: {[r.get(id_field) for r in list(rows)[:5]]}"
        )
    unknown = wanted - {str(r.get(id_field)) for r in rows}
    if unknown:
        raise RuntimeError(f"Unknown item id(s): {sorted(unknown)}")
    return filtered


def _installed_providers(request_fn: RequestFn) -> list[dict[str, Any]]:
    status, providers = request_fn("GET", "/providers", None)
    if status != 200:
        raise RuntimeError(f"Failed to list providers ({status}): {providers}")
    if isinstance(providers, dict):
        return list(providers.get("installed_providers") or providers.get("providers") or [])
    if isinstance(providers, list):
        return providers
    return []


def pick_temporal_provider_id(
    request_fn: RequestFn,
    preferred: str | None = None,
) -> str:
    if preferred:
        return preferred
    temporal = [
        p for p in _installed_providers(request_fn)
        if isinstance(p, dict) and p.get("type") == "temporal"
    ]
    if not temporal:
        raise RuntimeError(
            "No Temporal provider installed. Use the Temporal tab → Register Temporal first."
        )
    provider_id = temporal[0].get("id")
    if not provider_id:
        raise RuntimeError("Temporal provider is missing an id")
    return str(provider_id)


def upsert_temporal_catalog(
    request_fn: RequestFn,
    *,
    template: dict[str, Any],
    provider_id: str | None = None,
) -> dict[str, Any]:
    resolved_provider = pick_temporal_provider_id(request_fn, provider_id)
    payload = {**template, "provider_id": resolved_provider}
    status, existing = request_fn("GET", "/temporal-workflows", None)
    if status != 200:
        raise RuntimeError(f"Failed to list Temporal catalog ({status}): {existing}")
    match = None
    if isinstance(existing, list):
        match = next(
            (e for e in existing if e.get("catalog_key") == payload["catalog_key"]),
            None,
        )
    if match:
        status, result = request_fn(
            "PUT", f"/temporal-workflows/{match['id']}", payload
        )
        action = "updated"
    else:
        status, result = request_fn("POST", "/temporal-workflows", payload)
        action = "created"
    if status not in (200, 201):
        raise RuntimeError(f"Failed to register catalog ({status}): {result}")
    return {
        "ok": True,
        "action": action,
        "catalog_key": payload["catalog_key"],
        "provider_id": resolved_provider,
        "entry": result,
    }


def register_list_and_zip_catalog(
    request_fn: RequestFn, *, provider_id: str | None = None
) -> dict[str, Any]:
    return upsert_temporal_catalog(
        request_fn, template=LIST_AND_ZIP_CATALOG, provider_id=provider_id
    )


def register_nvidia_gpu_catalog(
    request_fn: RequestFn, *, provider_id: str | None = None
) -> dict[str, Any]:
    return upsert_temporal_catalog(
        request_fn, template=NVIDIA_GPU_CATALOG, provider_id=provider_id
    )


def register_probe_targets_catalog(
    request_fn: RequestFn, *, provider_id: str | None = None
) -> dict[str, Any]:
    return upsert_temporal_catalog(
        request_fn, template=PROBE_TARGETS_CATALOG, provider_id=provider_id
    )


def _list_alert_catalog(request_fn: RequestFn) -> dict[str, dict[str, Any]]:
    status, listed = request_fn("GET", "/alert-catalog", None)
    if status != 200:
        raise RuntimeError(f"Failed to list alert catalog ({status}): {listed}")
    if not isinstance(listed, list):
        return {}
    return {
        item.get("code"): item
        for item in listed
        if isinstance(item, dict) and item.get("code")
    }


def register_payments_alert_codes(
    request_fn: RequestFn,
    *,
    workflow_id: str = "mock-grafana-list-and-zip",
    codes: list[str] | None = None,
) -> dict[str, Any]:
    existing = _list_alert_catalog(request_fn)
    wf_status, _ = request_fn("GET", f"/workflows/{workflow_id}", None)
    keep_workflow_id = workflow_id if wf_status == 200 else None
    selected = _filter_by_ids(PAYMENTS_ALERT_CODES, id_field="code", selected=codes)

    created = 0
    skipped = 0
    for item in selected:
        code = item["code"]
        if code in existing:
            skipped += 1
            continue
        auto_run_on = "incident" if keep_workflow_id and code != "DISK_SPACE_LOW" else "none"
        linked = keep_workflow_id if auto_run_on != "none" else None
        if code == "DISK_SPACE_LOW":
            disk_status, _ = request_fn("GET", "/workflows/mock-mimir-disk", None)
            if disk_status == 200:
                linked = "mock-mimir-disk"
                auto_run_on = "both"
        payload = {
            **item,
            "keep_workflow_id": linked,
            "auto_run_on": auto_run_on,
            "disabled": False,
        }
        http_code, body = request_fn("POST", "/alert-catalog", payload)
        if http_code in (200, 201):
            created += 1
        elif http_code == 409:
            skipped += 1
        else:
            raise RuntimeError(f"Failed {code} ({http_code}): {body}")
    return {
        "ok": True,
        "created": created,
        "skipped": skipped,
        "total": len(selected),
        "codes": [item["code"] for item in selected],
    }


def register_nvidia_gpu_alert_codes(
    request_fn: RequestFn,
    *,
    workflow_id: str = "mock-nvidia-gpu-remediate",
    auto_run_on: str = "both",
    codes: list[str] | None = None,
) -> dict[str, Any]:
    existing = _list_alert_catalog(request_fn)
    wf_status, _ = request_fn("GET", f"/workflows/{workflow_id}", None)
    keep_workflow_id = workflow_id if wf_status == 200 else None
    selected = _filter_by_ids(NVIDIA_GPU_CODES, id_field="code", selected=codes)

    created = 0
    updated = 0
    skipped = 0
    for item in selected:
        code = item["code"]
        want_auto = (
            keep_workflow_id is not None
            and code in DEMO_AUTO_RUN_CODES
            and auto_run_on in {"alert", "incident", "both", "approval"}
        )
        payload = {
            **item,
            "keep_workflow_id": keep_workflow_id if want_auto else None,
            "auto_run_on": auto_run_on if want_auto else "none",
        }
        prior = existing.get(code)
        if prior is None:
            http_code, body = request_fn("POST", "/alert-catalog", payload)
            if http_code in (200, 201):
                created += 1
            elif http_code == 409:
                skipped += 1
            else:
                raise RuntimeError(f"Failed {code} ({http_code}): {body}")
            continue

        entry_id = prior.get("id")
        if entry_id is None:
            skipped += 1
            continue
        update_body = {
            "code": code,
            "name": item["name"],
            "description": item["description"],
            "runbook_url": item["runbook_url"],
            "tags": item["tags"],
            "domain": item.get("domain"),
            "role": item.get("role"),
            "disabled": bool(prior.get("disabled", False)),
            "keep_workflow_id": prior.get("keep_workflow_id")
            or (keep_workflow_id if want_auto else None),
            "auto_run_on": prior.get("auto_run_on")
            or (auto_run_on if want_auto else "none"),
        }
        http_code, body = request_fn("PUT", f"/alert-catalog/{entry_id}", update_body)
        if http_code == 200:
            updated += 1
        else:
            raise RuntimeError(f"Failed update {code} ({http_code}): {body}")
    return {
        "ok": True,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "total": len(selected),
        "codes": [item["code"] for item in selected],
    }


def register_nvidia_gpu_topology(request_fn: RequestFn) -> dict[str, Any]:
    result = apply_keep_topology(request_fn)
    created = result.get("services_created") or []
    return {
        "ok": True,
        "services_created": len(created),
        "dependencies_created": result.get("dependencies_created", 0),
        "application_created": result.get("application_created"),
        "detail": result,
    }


def _register_synth_alert_codes(
    request_fn: RequestFn,
    *,
    codes: list[str] | None = None,
) -> dict[str, int]:
    existing = set(_list_alert_catalog(request_fn).keys())
    selected = _filter_by_ids(SYNTH_ALERT_CODES, id_field="code", selected=codes)
    created = 0
    skipped = 0
    for item in selected:
        if item["code"] in existing:
            skipped += 1
            continue
        code, body = request_fn(
            "POST", "/alert-catalog", {**item, "disabled": False}
        )
        if code in (200, 201):
            created += 1
        elif code == 409:
            skipped += 1
        else:
            raise RuntimeError(f"Failed {item['code']} ({code}): {body}")
    return {"created": created, "skipped": skipped, "total": len(selected)}


def register_ai_dc_synthetic_checks(
    request_fn: RequestFn,
    *,
    provider_id: str | None = None,
    target_base_url: str | None = None,
    check_keys: list[str] | None = None,
) -> dict[str, Any]:
    resolved_provider = pick_temporal_provider_id(request_fn, provider_id)
    base_url = (
        target_base_url
        or os.environ.get("SYNTH_TARGET_BASE_URL")
        or "http://host.docker.internal:8099"
    ).rstrip("/")

    selected_specs = _filter_by_ids(PROBE_SPECS, id_field="id", selected=check_keys)
    alert_codes = [
        str(spec["code"]) for spec in selected_specs if spec.get("code")
    ]
    alert_stats = _register_synth_alert_codes(request_fn, codes=alert_codes or None)

    status, existing = request_fn("GET", "/synthetic-checks", None)
    if status != 200:
        raise RuntimeError(f"Failed to list synthetic checks ({status}): {existing}")
    by_key: dict[str, dict[str, Any]] = {}
    if isinstance(existing, list):
        by_key = {
            item.get("check_key"): item
            for item in existing
            if isinstance(item, dict) and item.get("check_key")
        }

    wanted_keys = {spec["id"] for spec in selected_specs}
    created = 0
    updated = 0
    failed = 0
    errors: list[str] = []
    registered_keys: list[str] = []
    for payload in build_keep_synthetic_checks(base_url, resolved_provider):
        key = payload["check_key"]
        if key not in wanted_keys:
            continue
        match = by_key.get(key)
        if match:
            code, body = request_fn("PUT", f"/synthetic-checks/{match['id']}", payload)
            action = "updated"
        else:
            code, body = request_fn("POST", "/synthetic-checks", payload)
            action = "created"
        if code not in (200, 201):
            failed += 1
            errors.append(f"{key} ({code}): {body}")
            continue
        registered_keys.append(key)
        if action == "created":
            created += 1
        else:
            updated += 1

    if failed:
        raise RuntimeError(
            f"AI DC synthetic checks failed={failed}: " + "; ".join(errors[:5])
        )
    return {
        "ok": True,
        "created": created,
        "updated": updated,
        "failed": failed,
        "base_url": base_url,
        "provider_id": resolved_provider,
        "alert_codes": alert_stats,
        "check_keys": registered_keys,
        "total": len(selected_specs),
    }


def upload_workflow(
    upload_fn: UploadFn,
    *,
    filename: str,
    content: bytes | None = None,
) -> dict[str, Any]:
    path = DEMO_WORKFLOWS_DIR / filename
    data = content if content is not None else path.read_bytes()
    status, body = upload_fn(
        "/workflows?lookup_by_name=true",
        filename,
        data,
        "application/x-yaml",
    )
    return {
        "ok": status < 400,
        "status": status,
        "filename": filename,
        "keep": body,
    }


def upload_workflows(
    upload_fn: UploadFn,
    *,
    filenames: list[str] | None = None,
) -> dict[str, Any]:
    available = {path.name: path for path in DEMO_WORKFLOWS_DIR.glob("*.yml")}
    if filenames:
        unknown = [name for name in filenames if name not in available]
        if unknown:
            raise RuntimeError(f"Unknown workflow file(s): {sorted(unknown)}")
        chosen = [available[name] for name in filenames]
    else:
        chosen = [available[name] for name in sorted(available)]
    results = [
        upload_workflow(upload_fn, filename=path.name) for path in chosen
    ]
    ok = all(item.get("ok") for item in results)
    return {
        "ok": ok,
        "uploaded": len(results),
        "workflows": results,
        "filenames": [path.name for path in chosen],
    }


def demo_list_and_zip(
    request_fn: RequestFn,
    upload_fn: UploadFn,
    *,
    provider_id: str | None = None,
) -> dict[str, Any]:
    steps: dict[str, Any] = {}
    steps["list_and_zip_catalog"] = register_list_and_zip_catalog(
        request_fn, provider_id=provider_id
    )
    steps["workflows"] = [
        upload_workflow(upload_fn, filename="mock-grafana-list-and-zip.yml"),
        upload_workflow(upload_fn, filename="mock-mimir-disk.yml"),
        upload_workflow(upload_fn, filename="mock-victoriametrics-memory.yml"),
        upload_workflow(upload_fn, filename="alert-code-console.yml"),
    ]
    steps["payments_alert_codes"] = register_payments_alert_codes(request_fn)
    return {"ok": True, "steps": steps}


def demo_nvidia_gpu(
    request_fn: RequestFn,
    upload_fn: UploadFn,
    *,
    provider_id: str | None = None,
    target_base_url: str | None = None,
) -> dict[str, Any]:
    steps: dict[str, Any] = {}
    steps["nvidia_gpu_catalog"] = register_nvidia_gpu_catalog(
        request_fn, provider_id=provider_id
    )
    steps["workflow"] = upload_workflow(
        upload_fn, filename="mock-nvidia-gpu-remediate.yml"
    )
    steps["nvidia_gpu_alert_codes"] = register_nvidia_gpu_alert_codes(request_fn)
    steps["nvidia_gpu_topology"] = register_nvidia_gpu_topology(request_fn)
    steps["ai_dc_synthetic_checks"] = register_ai_dc_synthetic_checks(
        request_fn,
        provider_id=provider_id,
        target_base_url=target_base_url,
    )
    return {"ok": True, "steps": steps}


ACTION_HANDLERS: dict[str, str] = {
    "list-and-zip-catalog": "register_list_and_zip_catalog",
    "nvidia-gpu-catalog": "register_nvidia_gpu_catalog",
    "probe-targets-catalog": "register_probe_targets_catalog",
    "payments-alert-codes": "register_payments_alert_codes",
    "nvidia-gpu-alert-codes": "register_nvidia_gpu_alert_codes",
    "nvidia-gpu-topology": "register_nvidia_gpu_topology",
    "ai-dc-synthetic-checks": "register_ai_dc_synthetic_checks",
    "demo-workflows": "upload_workflows",
    "demo-list-and-zip": "demo_list_and_zip",
    "demo-nvidia-gpu": "demo_nvidia_gpu",
}


def run_setup_action(
    action_id: str,
    request_fn: RequestFn,
    upload_fn: UploadFn | None = None,
    *,
    provider_id: str | None = None,
    target_base_url: str | None = None,
    items: list[str] | None = None,
) -> dict[str, Any]:
    if action_id not in ACTION_HANDLERS:
        raise KeyError(action_id)

    # Empty list means "nothing selected" — treat as error for selectable packs.
    selected = items if items else None

    if action_id == "list-and-zip-catalog":
        if selected and "list-and-zip-directory" not in selected:
            raise RuntimeError("Selected items do not include list-and-zip-directory")
        return register_list_and_zip_catalog(request_fn, provider_id=provider_id)
    if action_id == "nvidia-gpu-catalog":
        if selected and "remediate-nvidia-gpu" not in selected:
            raise RuntimeError("Selected items do not include remediate-nvidia-gpu")
        return register_nvidia_gpu_catalog(request_fn, provider_id=provider_id)
    if action_id == "probe-targets-catalog":
        if selected and "probe-targets" not in selected:
            raise RuntimeError("Selected items do not include probe-targets")
        return register_probe_targets_catalog(request_fn, provider_id=provider_id)
    if action_id == "payments-alert-codes":
        return register_payments_alert_codes(request_fn, codes=selected)
    if action_id == "nvidia-gpu-alert-codes":
        return register_nvidia_gpu_alert_codes(request_fn, codes=selected)
    if action_id == "nvidia-gpu-topology":
        return register_nvidia_gpu_topology(request_fn)
    if action_id == "ai-dc-synthetic-checks":
        return register_ai_dc_synthetic_checks(
            request_fn,
            provider_id=provider_id,
            target_base_url=target_base_url,
            check_keys=selected,
        )
    if upload_fn is None:
        raise RuntimeError(f"Action {action_id} requires workflow upload support")
    if action_id == "demo-workflows":
        return upload_workflows(upload_fn, filenames=selected)
    if action_id == "demo-list-and-zip":
        return demo_list_and_zip(request_fn, upload_fn, provider_id=provider_id)
    if action_id == "demo-nvidia-gpu":
        return demo_nvidia_gpu(
            request_fn,
            upload_fn,
            provider_id=provider_id,
            target_base_url=target_base_url,
        )
    raise KeyError(action_id)
