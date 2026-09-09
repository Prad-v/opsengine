"""Realistic webhook payloads for Grafana, Mimir Alertmanager, and VictoriaMetrics."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

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


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _fingerprint(labels: dict[str, Any]) -> str:
    src = json.dumps(labels, sort_keys=True)
    return hashlib.md5(src.encode()).hexdigest()


def build_alertmanager_alert(
    *,
    alertname: str,
    severity: str = "critical",
    status: str = "firing",
    summary: str | None = None,
    description: str | None = None,
    extra_labels: dict[str, str] | None = None,
) -> dict[str, Any]:
    labels = {
        "alertname": alertname,
        "severity": severity,
        "instance": "mock-instance-1",
        "job": "provider-mock",
        "service": "payments-api",
        **(extra_labels or {}),
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

    return {
        "receiver": "keep-webhook",
        "status": status,
        "alerts": [alert],
        "groupLabels": {"alertname": alertname, "service": service},
        "commonLabels": {
            "alertname": alertname,
            "severity": severity,
            "service": service,
            "host": host,
            "cluster": cluster,
            "grafana_folder": "Provider Mock",
        },
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


# Two Grafana alerts that share service/cluster so Keep can correlate them into one incident.
GRAFANA_SCENARIOS: dict[str, dict[str, Any]] = {
    "cpu": {
        "id": "cpu",
        "label": "Payload A — High CPU",
        "description": "MockHighCPU on payments-api / srv-payments-1 (warning).",
        "builder_kwargs": {
            "alertname": "MockHighCPU",
            "severity": "warning",
            "service": "payments-api",
            "host": "srv-payments-1",
            "cluster": "mock-prod",
            "summary": "CPU above 90% on payments API host",
            "description": "Grafana mock payload A: High CPU on payments-api.",
        },
    },
    "memory": {
        "id": "memory",
        "label": "Payload B — High Memory",
        "description": "MockHighMemory on payments-api / srv-payments-1 (critical).",
        "builder_kwargs": {
            "alertname": "MockHighMemory",
            "severity": "critical",
            "service": "payments-api",
            "host": "srv-payments-1",
            "cluster": "mock-prod",
            "summary": "Memory above 85% on payments API host",
            "description": "Grafana mock payload B: High Memory on payments-api.",
        },
    },
}

GRAFANA_CORRELATION_RULE: dict[str, Any] = {
    "ruleName": "Grafana mock payments incident",
    "groupDescription": (
        "Correlates the two Grafana mock payloads (High CPU + High Memory) "
        "that share labels.service=payments-api and labels.cluster=mock-prod."
    ),
    "celQuery": 'source == "grafana" && labels.cluster == "mock-prod"',
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
    "incidentNameTemplate": "Payments degradation ({{ alert.labels.service }})",
    "incidentPrefix": "INC",
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
        extra_labels={"cluster": "mock-mimir", "namespace": "observability"},
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
        extra_labels={"cluster": "mock-vm", "env": "local"},
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
