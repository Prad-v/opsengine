"""Mock and catalog workflows trigger on reserved labels.code / incident.code."""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from uuid import uuid4

import celpy
import pytest

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.api.models.incident import IncidentDto
from keep.api.utils.alert_code import normalize_alert_code
from keep.api.utils.cel_utils import preprocess_cel_expression
from keep.functions import cyaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / "examples" / "workflows"

MOCK_WORKFLOW_FILES = (
    "mock-grafana-list-and-zip.yml",
    "mock-nvidia-gpu-remediate.yml",
    "mock-mimir-disk.yml",
    "mock-victoriametrics-memory.yml",
    "alert-code-console.yml",
    "incident-to-temporal.yml",
    "ai-dc-synthetic-firing.yml",
)


def _eval_cel(cel: str, payload: dict) -> bool:
    env = celpy.Environment()
    program = env.program(env.compile(preprocess_cel_expression(cel)))
    return bool(program.evaluate(celpy.json_to_cel(payload)))


def _triggers(path: Path) -> list[dict]:
    data = cyaml.safe_load(path.read_text())
    return list((data.get("workflow") or data).get("triggers") or [])


def _alert(**kwargs) -> AlertDto:
    body = {
        "id": "test-alert",
        "source": ["grafana"],
        "name": "test",
        "status": AlertStatus.FIRING,
        "severity": AlertSeverity.WARNING,
        "lastReceived": datetime.datetime.utcnow().isoformat(),
        "fingerprint": "fp-test",
        "labels": {},
    }
    body.update(kwargs)
    alert = AlertDto(**body)
    normalize_alert_code(alert)
    return alert


def _incident(**kwargs) -> IncidentDto:
    body = {
        "id": uuid4(),
        "user_generated_name": "test-incident",
        "alerts_count": 1,
        "alert_sources": ["grafana"],
        "services": ["payments-api"],
        "severity": "critical",
        "is_predicted": False,
        "is_candidate": False,
    }
    body.update(kwargs)
    return IncidentDto(**body)


def _alert_payload(alert: AlertDto) -> dict:
    payload = alert.dict()
    if isinstance(payload.get("severity"), str):
        try:
            payload["severity"] = AlertSeverity(payload["severity"].lower()).order
        except (ValueError, AttributeError):
            pass
    status = payload.get("status")
    if hasattr(status, "value"):
        payload["status"] = status.value
    return payload


def _incident_payload(incident: IncidentDto) -> dict:
    payload = json.loads(incident.json())
    payload["name"] = incident.name
    payload["code"] = payload.get("code") or ""
    payload["codes"] = payload.get("codes") or []
    return payload


def test_all_example_workflows_parse():
    files = list(WORKFLOWS.glob("*.yml")) + list(WORKFLOWS.glob("*.yaml"))
    assert len(files) >= 100
    for path in files:
        data = cyaml.safe_load(path.read_text())
        assert data, path.name
        workflow = data.get("workflow") or data
        assert workflow.get("id"), path.name
        assert workflow.get("triggers"), path.name


def test_mock_workflows_trigger_on_reserved_code():
    for name in MOCK_WORKFLOW_FILES:
        path = WORKFLOWS / name
        assert path.is_file(), name
        cels = " ".join(trigger.get("cel") or "" for trigger in _triggers(path))
        assert "code" in cels, f"{name} must filter on reserved code"


@pytest.mark.parametrize(
    "filename,alert_code,incident_codes,should_match",
    [
        ("mock-grafana-list-and-zip.yml", "HIGH_CPU", ["HIGH_CPU", "HIGH_MEMORY"], True),
        (
            "mock-grafana-list-and-zip.yml",
            "NVIDIA_GPU_THERMAL",
            ["NVIDIA_GPU_THERMAL"],
            False,
        ),
        (
            "mock-nvidia-gpu-remediate.yml",
            "NVIDIA_GPU_THERMAL",
            ["NVIDIA_GPU_THERMAL"],
            True,
        ),
        ("mock-nvidia-gpu-remediate.yml", "HIGH_CPU", ["HIGH_CPU"], False),
        ("mock-mimir-disk.yml", "DISK_SPACE_LOW", ["DISK_SPACE_LOW"], True),
        ("mock-mimir-disk.yml", "HIGH_CPU", ["HIGH_CPU"], False),
        ("mock-victoriametrics-memory.yml", "HIGH_MEMORY", ["HIGH_MEMORY"], True),
        ("mock-victoriametrics-memory.yml", "NVIDIA_GPU_XID", ["NVIDIA_GPU_XID"], False),
        ("alert-code-console.yml", "HIGH_CPU", ["HIGH_CPU"], True),
        ("incident-to-temporal.yml", "HIGH_CPU", ["HIGH_CPU"], True),
        ("incident-to-temporal.yml", None, [], False),
        (
            "ai-dc-synthetic-firing.yml",
            "SYNTH_NVIDIA_INFERENCE_GOLDEN",
            ["SYNTH_NVIDIA_INFERENCE_GOLDEN"],
            True,
        ),
        (
            "ai-dc-synthetic-firing.yml",
            "NVIDIA_GPU_THERMAL",
            ["NVIDIA_GPU_THERMAL"],
            False,
        ),
    ],
)
def test_mock_workflow_cel_matches_codes(
    filename, alert_code, incident_codes, should_match
):
    triggers = _triggers(WORKFLOWS / filename)
    alert = _alert(
        name=alert_code or "none",
        labels={"code": alert_code} if alert_code else {},
        status=AlertStatus.FIRING,
    )
    incident = _incident(
        code=incident_codes[0] if incident_codes else None,
        codes=incident_codes or None,
    )
    alert_payload = _alert_payload(alert)
    incident_payload = _incident_payload(incident)

    matched = False
    for trigger in triggers:
        cel = trigger.get("cel")
        if not cel:
            matched = True
            continue
        payload = (
            incident_payload if trigger.get("type") == "incident" else alert_payload
        )
        if _eval_cel(cel, payload):
            matched = True
    assert matched is should_match, f"{filename} code={alert_code}"
