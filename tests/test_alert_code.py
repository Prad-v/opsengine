from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.api.utils.alert_code import (
    collect_codes,
    get_alert_code,
    merge_incident_codes,
    normalize_alert_code,
    slugify_alert_code,
)


def _alert(**kwargs) -> AlertDto:
    payload = {
        "name": "Pod lacks memory",
        "status": AlertStatus.FIRING,
        "severity": AlertSeverity.CRITICAL,
        "lastReceived": "2026-09-13T00:00:00.000Z",
        "source": ["grafana"],
        "labels": {},
    }
    payload.update(kwargs)
    return AlertDto(**payload)


def test_slugify_alert_code_splits_camel_and_uppercases():
    assert slugify_alert_code("NvidiaGpuHighTemperature") == "NVIDIA_GPU_HIGH_TEMPERATURE"
    assert slugify_alert_code("high-cpu") == "HIGH_CPU"
    assert slugify_alert_code("  nvidia_gpu_thermal  ") == "NVIDIA_GPU_THERMAL"
    assert slugify_alert_code("HTTP_5XX") == "HTTP_5XX"
    assert slugify_alert_code("") == ""
    assert slugify_alert_code(None) == ""


def test_normalize_mirrors_labels_code_to_top_level():
    alert = _alert(labels={"code": "nvidia_gpu_thermal", "host": "gpu-node-a03"})
    assert normalize_alert_code(alert) == "NVIDIA_GPU_THERMAL"
    assert alert.code == "NVIDIA_GPU_THERMAL"
    assert alert.labels["code"] == "NVIDIA_GPU_THERMAL"


def test_normalize_mirrors_top_level_code_into_labels():
    alert = _alert(code="HIGH_CPU", labels={"service": "payments-api"})
    assert normalize_alert_code(alert) == "HIGH_CPU"
    assert alert.labels["code"] == "HIGH_CPU"
    assert alert.code == "HIGH_CPU"


def test_normalize_does_not_invent_code_from_name():
    alert = _alert(name="GPU temperature critical")
    assert normalize_alert_code(alert) is None
    assert alert.code is None
    assert "code" not in (alert.labels or {})


def test_get_alert_code_from_dict_payload():
    assert get_alert_code({"labels": {"code": "HTTP_5XX"}}) == "HTTP_5XX"
    assert get_alert_code({"code": "disk_full"}) == "DISK_FULL"


def test_grafana_format_preserves_reserved_code():
    from keep.providers.grafana_provider.grafana_provider import GrafanaProvider

    event = {
        "status": "firing",
        "title": "GPU temperature above 85C",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "code": "NVIDIA_GPU_THERMAL",
                    "severity": "critical",
                    "alertname": "NvidiaGpuHighTemperature",
                },
                "annotations": {"description": "DCGM temp exceeded"},
                "fingerprint": "gpu-temp-1",
            }
        ],
    }
    alerts = GrafanaProvider._format_alert(event)
    assert isinstance(alerts, list)
    assert alerts[0].labels["code"] == "NVIDIA_GPU_THERMAL"
    assert normalize_alert_code(alerts[0]) == "NVIDIA_GPU_THERMAL"
    assert alerts[0].code == "NVIDIA_GPU_THERMAL"


def test_collect_and_merge_incident_codes():
    alerts = [
        _alert(labels={"code": "NVIDIA_GPU_THERMAL"}),
        _alert(labels={"code": "NVIDIA_GPU_MEMORY"}),
        _alert(labels={"code": "NVIDIA_GPU_THERMAL"}),
    ]
    codes = collect_codes(alerts)
    assert codes == ["NVIDIA_GPU_THERMAL", "NVIDIA_GPU_MEMORY"]
    primary, merged = merge_incident_codes(["NVIDIA_GPU_THERMAL"], ["NVIDIA_GPU_MEMORY"])
    assert merged == ["NVIDIA_GPU_THERMAL", "NVIDIA_GPU_MEMORY"]
    assert primary == "NVIDIA_GPU_THERMAL"
    only_primary, only_codes = merge_incident_codes([], ["HIGH_CPU"])
    assert only_primary == "HIGH_CPU"
    assert only_codes == ["HIGH_CPU"]
