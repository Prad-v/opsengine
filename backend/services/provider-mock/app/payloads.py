"""Realistic webhook payloads for Grafana, Mimir Alertmanager, and VictoriaMetrics."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from app.gpu_topology import location_for_scenario

ProviderKey = Literal["grafana", "mimir", "victoriametrics", "temporal"]

PROVIDER_CATALOG: dict[ProviderKey, dict[str, Any]] = {
    "grafana": {
        "label": "Grafana",
        "keep_type": "grafana",
        "description": "Grafana Alerting webhook (Alertmanager-compatible group).",
        "default_name": "mock-grafana",
        "kind": "alert",
        "supports_events": True,
    },
    "mimir": {
        "label": "Mimir Alertmanager",
        "keep_type": "prometheus",
        "description": "Grafana Mimir / Prometheus Alertmanager webhook (Keep type: prometheus).",
        "default_name": "mock-mimir-alertmanager",
        "kind": "alert",
        "supports_events": True,
    },
    "victoriametrics": {
        "label": "VictoriaMetrics",
        "keep_type": "victoriametrics",
        "description": "VictoriaMetrics / VMAlert Alertmanager-compatible webhook.",
        "default_name": "mock-victoriametrics",
        "kind": "alert",
        "supports_events": True,
    },
    "temporal": {
        "label": "Temporal",
        "keep_type": "temporal",
        "description": "Register Keep's Temporal provider against the local Docker Compose Temporal server.",
        "default_name": "mock-temporal",
        "kind": "orchestration",
        "supports_events": False,
    },
}

ALERT_PROVIDER_KEYS: tuple[ProviderKey, ...] = (
    "grafana",
    "mimir",
    "victoriametrics",
)

# Reserved labels.code for default mock alert names (source-agnostic UPPER_SNAKE).
DEFAULT_ALERT_CODES: dict[str, str] = {
    "MockHighCPU": "HIGH_CPU",
    "MockHighMemory": "HIGH_MEMORY",
    "MockDiskSpaceLow": "DISK_SPACE_LOW",
}

PAYMENTS_CODES: tuple[str, ...] = ("HIGH_CPU", "HIGH_MEMORY")
NVIDIA_GPU_CODE_PREFIX = "NVIDIA_GPU"


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _fingerprint(labels: dict[str, Any]) -> str:
    src = json.dumps(labels, sort_keys=True)
    return hashlib.md5(src.encode()).hexdigest()


def slugify_alert_code(value: str) -> str:
    """Reserved mock `code` from an alert name (UPPER_SNAKE, splits camelCase)."""
    raw = value or ""
    if re.fullmatch(r"[A-Z0-9_]+", raw):
        return re.sub(r"_+", "_", raw).strip("_") or "UNKNOWN"
    split_camel = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", raw)
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", split_camel).strip("_")
    return slug.upper() or "UNKNOWN"


def build_alertmanager_alert(
    *,
    alertname: str,
    severity: str = "critical",
    status: str = "firing",
    summary: str | None = None,
    description: str | None = None,
    extra_labels: dict[str, str] | None = None,
) -> dict[str, Any]:
    extra = dict(extra_labels or {})
    if "code" not in extra:
        extra["code"] = DEFAULT_ALERT_CODES.get(alertname) or slugify_alert_code(
            alertname
        )
    labels = {
        "alertname": alertname,
        "severity": severity,
        "instance": "mock-instance-1",
        "job": "provider-mock",
        "service": "payments-api",
        **extra,
    }
    fingerprint = _fingerprint(labels)
    return {
        "status": status,
        "labels": labels,
        "annotations": {
            "summary": summary or f"{alertname}: simulated by provider-mock",
            "description": description
            or f"E2E mock alert for {alertname} ({severity})",
        },
        "startsAt": _now_iso(),
        "endsAt": "0001-01-01T00:00:00Z"
        if status == "firing"
        else _now_iso(),
        "generatorURL": f"http://provider-mock.local/graph?g0.expr={alertname}",
        "fingerprint": fingerprint,
    }


def build_grafana_payload(
    *,
    status: str = "firing",
    alertname: str = "MockHighCPU",
    severity: str = "warning",
    service: str = "payments-api",
    host: str = "srv-payments-1",
    cluster: str = "mock-prod",
    summary: str | None = None,
    description: str | None = None,
    extra_labels: dict[str, str] | None = None,
) -> dict[str, Any]:
    labels_extra = {
        "grafana_folder": "Provider Mock",
        "datasource_uid": "mock-prom",
        "service": service,
        "host": host,
        "cluster": cluster,
        **(extra_labels or {}),
    }
    alert = build_alertmanager_alert(
        alertname=alertname,
        severity=severity,
        status=status,
        summary=summary or f"Grafana mock: {alertname} on {host}",
        description=description
        or f"Simulated Grafana alert {alertname} for service {service} (cluster {cluster}).",
        extra_labels=labels_extra,
    )
    # Override default service label from build_alertmanager_alert
    alert["labels"]["service"] = service
    alert["labels"]["host"] = host
    alert["labels"]["cluster"] = cluster
    alert["silenceURL"] = "https://mock-grafana.local/alerting/silence/new"
    alert["dashboardURL"] = "https://mock-grafana.local/d/mock-dashboard"
    alert["panelURL"] = "https://mock-grafana.local/d/mock-dashboard?viewPanel=1"
    alert["values"] = {"B": 92.5 if "CPU" in alertname else 87.1, "C": 1}
    alert["valueString"] = f"[ var='B' value={alert['values']['B']} ]"
    alert["orgId"] = 1
    # Stable fingerprint for the scenario so repeats dedupe; different scenarios differ.
    alert["fingerprint"] = _fingerprint(alert["labels"])

    common_labels = {
        "alertname": alertname,
        "severity": severity,
        "service": service,
        "host": host,
        "cluster": cluster,
        "grafana_folder": "Provider Mock",
        "code": alert["labels"].get("code") or slugify_alert_code(alertname),
        **(extra_labels or {}),
    }
    return {
        "receiver": "keep-webhook",
        "status": status,
        "alerts": [alert],
        "groupLabels": {"alertname": alertname, "service": service},
        "commonLabels": common_labels,
        "commonAnnotations": {
            "summary": alert["annotations"]["summary"],
            "description": alert["annotations"]["description"],
        },
        "externalURL": "https://mock-grafana.local/",
        "version": "1",
        "groupKey": f"mock-{alertname}-{service}",
        "truncatedAlerts": 0,
        "orgId": 1,
        "title": f"[FIRING:1] {alertname}"
        if status == "firing"
        else f"[RESOLVED] {alertname}",
        "state": "alerting" if status == "firing" else "ok",
        "message": "Firing" if status == "firing" else "Resolved",
    }


def _gpu_location_labels(scenario_id: str) -> dict[str, str]:
    return location_for_scenario(scenario_id)


def _gpu_scenario(
    *,
    scenario_id: str,
    label: str,
    alertname: str,
    severity: str,
    summary: str,
    description: str,
    dcgm_field: str,
    value: float,
    extra: dict[str, str] | None = None,
) -> dict[str, Any]:
    loc = _gpu_location_labels(scenario_id)
    extra_labels = {
        key: loc[key]
        for key in (
            "region",
            "datacenter",
            "row",
            "rack",
            "gpu",
            "gpu_id",
            "gpu_uuid",
            "gpu_model",
            "namespace",
            "vendor",
        )
    }
    extra_labels["dcgm_field"] = dcgm_field
    extra_labels.update(extra or {})
    return {
        "id": scenario_id,
        "label": label,
        "description": description,
        "pack": "nvidia-gpu",
        "builder_kwargs": {
            "alertname": alertname,
            "severity": severity,
            "service": loc["service"],
            "host": loc["host"],
            "cluster": loc["cluster"],
            "summary": summary,
            "description": description,
            "extra_labels": extra_labels,
        },
        "values": {"B": value, "C": 1},
    }


# Two Grafana alerts that share service/cluster so Keep can correlate them into one incident.
GRAFANA_PAYMENTS_SCENARIOS: dict[str, dict[str, Any]] = {
    "cpu": {
        "id": "cpu",
        "label": "Payload A — High CPU",
        "description": "MockHighCPU on payments-api / srv-payments-1 (warning).",
        "pack": "payments",
        "builder_kwargs": {
            "alertname": "MockHighCPU",
            "severity": "warning",
            "service": "payments-api",
            "host": "srv-payments-1",
            "cluster": "mock-prod",
            "summary": "CPU above 90% on payments API host",
            "description": "Grafana mock payload A: High CPU on payments-api.",
            "extra_labels": {"code": "HIGH_CPU"},
        },
    },
    "memory": {
        "id": "memory",
        "label": "Payload B — High Memory",
        "description": "MockHighMemory on payments-api / srv-payments-1 (critical).",
        "pack": "payments",
        "builder_kwargs": {
            "alertname": "MockHighMemory",
            "severity": "critical",
            "service": "payments-api",
            "host": "srv-payments-1",
            "cluster": "mock-prod",
            "summary": "Memory above 85% on payments API host",
            "description": "Grafana mock payload B: High Memory on payments-api.",
            "extra_labels": {"code": "HIGH_MEMORY"},
        },
    },
}

# NVIDIA GPU / DCGM-style alerts for AI datacenter Keep HQ demos.
GRAFANA_GPU_SCENARIOS: dict[str, dict[str, Any]] = {
    "gpu_temp": _gpu_scenario(
        scenario_id="gpu_temp",
        label="GPU — High temperature",
        alertname="NvidiaGpuHighTemperature",
        severity="critical",
        summary="GPU temperature above 85°C on H100 (gpu-node-a03 / row-a / rack-12)",
        description=(
            "DCGM mock: DCGM_FI_DEV_GPU_TEMP exceeded threshold on NVIDIA H100 "
            "in us-west-2 / ai-dc-1 / row-a / rack-12 / gpu-node-a03-gpu0."
        ),
        dcgm_field="DCGM_FI_DEV_GPU_TEMP",
        value=91.0,
        extra={"code": "NVIDIA_GPU_THERMAL"},
    ),
    "gpu_mem": _gpu_scenario(
        scenario_id="gpu_mem",
        label="GPU — High memory utilization",
        alertname="NvidiaGpuHighMemoryUtilization",
        severity="warning",
        summary="GPU framebuffer utilization above 95% on H100 (gpu-node-a03)",
        description=(
            "DCGM mock: DCGM_FI_DEV_FB_USED near capacity for inference workload "
            "on gpu-node-a03 / row-a / rack-12."
        ),
        dcgm_field="DCGM_FI_DEV_FB_USED",
        value=97.2,
        extra={"code": "NVIDIA_GPU_MEMORY"},
    ),
    "gpu_xid": _gpu_scenario(
        scenario_id="gpu_xid",
        label="GPU — XID error",
        alertname="NvidiaGpuXidError",
        severity="critical",
        summary="NVIDIA XID error detected on gpu-node-a03-gpu1 (rack-12)",
        description=(
            "DCGM mock: DCGM_FI_DEV_XID_ERRORS reported on gpu-node-a03 / "
            "row-a / rack-12 / GPU 1; check nvidia-smi and kernel logs."
        ),
        dcgm_field="DCGM_FI_DEV_XID_ERRORS",
        value=79.0,
        extra={"xid_code": "79", "code": "NVIDIA_GPU_XID"},
    ),
    "gpu_ecc": _gpu_scenario(
        scenario_id="gpu_ecc",
        label="GPU — Uncorrectable ECC",
        alertname="NvidiaGpuUncorrectableEcc",
        severity="critical",
        summary="Uncorrectable ECC errors on H100 HBM (gpu-node-a01 / rack-11)",
        description=(
            "DCGM mock: DCGM_FI_DEV_ECC_DBE_VOL_TOTAL increased on "
            "gpu-node-a01 / row-a / rack-11; schedule GPU quarantine / RMA."
        ),
        dcgm_field="DCGM_FI_DEV_ECC_DBE_VOL_TOTAL",
        value=3.0,
        extra={"code": "NVIDIA_GPU_ECC"},
    ),
    "gpu_throttle": _gpu_scenario(
        scenario_id="gpu_throttle",
        label="GPU — Thermal throttle",
        alertname="NvidiaGpuThermalThrottle",
        severity="warning",
        summary="GPU clocks thermally throttled (gpu-node-a01-gpu1 / row-a)",
        description=(
            "DCGM mock: DCGM_FI_DEV_CLOCK_THROTTLE_REASONS indicates thermal "
            "limit on gpu-node-a01 / row-a / rack-11; check cooling / airflow."
        ),
        dcgm_field="DCGM_FI_DEV_CLOCK_THROTTLE_REASONS",
        value=1.0,
        extra={"code": "NVIDIA_GPU_THROTTLE"},
    ),
    "gpu_nvlink": _gpu_scenario(
        scenario_id="gpu_nvlink",
        label="GPU — NVLink error",
        alertname="NvidiaNvlinkError",
        severity="critical",
        summary="NVLink CRC / flit errors on gpu-node-b01 (row-b / rack-21)",
        description=(
            "DCGM mock: DCGM_FI_DEV_NVLINK_CRC_FLIT_ERROR_COUNT_TOTAL rising on "
            "gpu-node-b01 / row-b / rack-21; inspect NVLink fabric and cables."
        ),
        dcgm_field="DCGM_FI_DEV_NVLINK_CRC_FLIT_ERROR_COUNT_TOTAL",
        value=12.0,
        extra={"code": "NVIDIA_GPU_NVLINK"},
    ),
    "gpu_power": _gpu_scenario(
        scenario_id="gpu_power",
        label="GPU — Power limit",
        alertname="NvidiaGpuPowerLimitExceeded",
        severity="warning",
        summary="GPU power draw near / at power limit (gpu-node-b01-gpu1)",
        description=(
            "DCGM mock: DCGM_FI_DEV_POWER_USAGE sustained near configured power "
            "limit on H100 in us-west-2 / ai-dc-1 / row-b / rack-21."
        ),
        dcgm_field="DCGM_FI_DEV_POWER_USAGE",
        value=698.0,
        extra={"code": "NVIDIA_GPU_POWER"},
    ),
    "gpu_unavailable": _gpu_scenario(
        scenario_id="gpu_unavailable",
        label="GPU — Unavailable / lost",
        alertname="NvidiaGpuUnavailable",
        severity="critical",
        summary="GPU not ready — driver lost on gpu-node-a03 / rack-12",
        description=(
            "Mock node-level alert: nvidia device disappeared or DCGM health "
            "check failed on gpu-node-a03 / row-a / rack-12 / gpu-node-a03-gpu0."
        ),
        dcgm_field="DCGM_FI_DEV_HEALTH",
        value=0.0,
        extra={"health": "fail", "code": "NVIDIA_GPU_UNAVAILABLE"},
    ),
}

GRAFANA_SCENARIOS: dict[str, dict[str, Any]] = {
    **GRAFANA_PAYMENTS_SCENARIOS,
    **GRAFANA_GPU_SCENARIOS,
}

# Default pair fired by the NVIDIA GPU incident demo (threshold=2).
GRAFANA_GPU_DEMO_SCENARIO_IDS: tuple[str, ...] = ("gpu_temp", "gpu_mem")

GRAFANA_CORRELATION_RULE: dict[str, Any] = {
    "ruleName": "Grafana mock payments incident",
    "groupDescription": (
        "Correlates Grafana mock payloads with reserved labels.code HIGH_CPU "
        "or HIGH_MEMORY that share labels.service=payments-api."
    ),
    "celQuery": (
        'source == "grafana" && labels.cluster == "mock-prod" && '
        '(labels.code == "HIGH_CPU" || labels.code == "HIGH_MEMORY")'
    ),
    "sqlQuery": {
        "sql": "((source = :source_1))",
        "params": {"source_1": "grafana"},
    },
    "timeframeInSeconds": 86400,
    "timeUnit": "hours",
    "groupingCriteria": ["labels.service"],
    "requireApprove": False,
    "resolveOn": "never",
    "createOn": "any",
    # Visible once both mock payloads land on the same grouped incident.
    "threshold": 2,
    "incidentNameTemplate": (
        "Payments {{ alert.labels.code }} ({{ alert.labels.service }})"
    ),
    "incidentPrefix": "INC",
}

GRAFANA_GPU_CORRELATION_RULE: dict[str, Any] = {
    "ruleName": "NVIDIA GPU cluster incident",
    "groupDescription": (
        "Correlates NVIDIA / DCGM Grafana mock alerts whose reserved "
        "labels.code starts with NVIDIA_GPU, grouped by labels.host "
        "(region/row/rack/gpu on labels)."
    ),
    "celQuery": (
        'source == "grafana" && labels.cluster == "ai-dc-prod" '
        '&& labels.vendor == "nvidia" && labels.code.startsWith("NVIDIA_GPU")'
    ),
    "sqlQuery": {
        "sql": "((source = :source_1))",
        "params": {"source_1": "grafana"},
    },
    "timeframeInSeconds": 86400,
    "timeUnit": "hours",
    "groupingCriteria": ["labels.host"],
    "requireApprove": False,
    "resolveOn": "never",
    "createOn": "any",
    "threshold": 2,
    "incidentNameTemplate": (
        "GPU {{ alert.labels.code }} ({{ alert.labels.host }})"
    ),
    "incidentPrefix": "GPU",
}


def build_grafana_scenario_payload(
    scenario_id: str,
    *,
    status: str = "firing",
    run_id: str | None = None,
) -> dict[str, Any]:
    scenario = GRAFANA_SCENARIOS.get(scenario_id)
    if not scenario:
        raise ValueError(
            f"Unknown Grafana scenario '{scenario_id}'. "
            f"Choose one of: {', '.join(GRAFANA_SCENARIOS)}"
        )
    payload = build_grafana_payload(status=status, **scenario["builder_kwargs"])
    # Optional DCGM-style numeric values for GPU scenarios.
    values = scenario.get("values")
    if values:
        for alert in payload["alerts"]:
            alert["values"] = values
            alert["valueString"] = f"[ var='B' value={values.get('B')} ]"
    if run_id:
        # Unique fingerprints per demo run so re-sends create fresh alerts.
        for alert in payload["alerts"]:
            alert["labels"]["demo_run"] = run_id
            alert["fingerprint"] = _fingerprint(alert["labels"])
        payload["commonLabels"]["demo_run"] = run_id
    return payload


def build_mimir_payload(
    *,
    status: str = "firing",
    alertname: str = "MockDiskSpaceLow",
    severity: str = "critical",
) -> dict[str, Any]:
    alert = build_alertmanager_alert(
        alertname=alertname,
        severity=severity,
        status=status,
        summary=f"Mimir Alertmanager mock: {alertname}",
        description="Simulated Mimir / Prometheus Alertmanager webhook.",
        extra_labels={
            "cluster": "mock-mimir",
            "namespace": "observability",
            "code": "DISK_SPACE_LOW",
        },
    )
    return {
        "receiver": "keep",
        "status": status,
        "alerts": [alert],
        "groupLabels": {"alertname": alertname},
        "commonLabels": alert["labels"],
        "commonAnnotations": alert["annotations"],
        "externalURL": "http://mock-mimir-alertmanager.local",
        "version": "4",
        "groupKey": f"{{}}:{uuid.uuid4().hex[:12]}",
        "truncatedAlerts": 0,
    }


def build_victoriametrics_payload(
    *,
    status: str = "firing",
    alertname: str = "MockHighMemory",
    severity: str = "critical",
) -> dict[str, Any]:
    alert = build_alertmanager_alert(
        alertname=alertname,
        severity=severity,
        status=status,
        summary=f"VictoriaMetrics mock: {alertname}",
        description="Simulated VMAlert / VictoriaMetrics webhook.",
        extra_labels={
            "cluster": "mock-vm",
            "env": "local",
            "code": "HIGH_MEMORY",
        },
    )
    return {
        "receiver": "keep",
        "status": status,
        "alerts": [alert],
        "groupLabels": {"alertname": alertname},
        "commonLabels": alert["labels"],
        "commonAnnotations": alert["annotations"],
        "externalURL": "http://mock-vmalert.local",
        "version": "4",
        "groupKey": f"vm-{uuid.uuid4().hex[:8]}",
        "truncatedAlerts": 0,
    }


def build_payload(
    provider: ProviderKey,
    *,
    status: str = "firing",
    alertname: str | None = None,
    severity: str | None = None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"status": status}
    if alertname:
        kwargs["alertname"] = alertname
    if severity:
        kwargs["severity"] = severity

    if provider == "grafana":
        return build_grafana_payload(**kwargs)
    if provider == "mimir":
        return build_mimir_payload(**kwargs)
    if provider == "victoriametrics":
        return build_victoriametrics_payload(**kwargs)
    if provider == "temporal":
        raise ValueError(
            "Temporal is an action provider; it does not ingest alert webhook events"
        )
    raise ValueError(f"Unknown provider: {provider}")
