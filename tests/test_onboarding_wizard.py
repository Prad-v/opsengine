"""API contract used by the Keep alert lifecycle table and wizard.

The UI lists catalog rows as lifecycles, then compose existing endpoints:
alert catalog, correlation rules, and YAML workflows keyed on reserved labels.code.
Pause sets catalog.disabled; delete removes the catalog row and matching rule.
"""

from __future__ import annotations

import pytest

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.db.workflow import Workflow
from tests.fixtures.client import client, setup_api_key, test_app  # noqa

ONBOARDING_WORKFLOW_YAML = """
workflow:
  id: onboarding-notify-high-cpu
  name: Notify on HIGH_CPU
  description: Created by the setup wizard for reserved alert code HIGH_CPU.
  triggers:
    - type: alert
      cel: has(labels.code) && labels.code == "HIGH_CPU" && status == "firing"
    - type: incident
      events:
        - created
      cel: code == "HIGH_CPU"
  actions:
    - name: notify-oncall
      provider:
        type: console
        with:
          message: "{{ alert.labels.code or incident.code }} — {{ alert.name or incident.name }}"
"""

CORRELATION_PAYLOAD = {
    "ruleName": "Correlate HIGH_CPU",
    "groupDescription": "Groups alerts whose reserved labels.code is HIGH_CPU.",
    "celQuery": 'has(labels.code) && labels.code == "HIGH_CPU"',
    "sqlQuery": {
        "sql": "((labels.code = :code_1))",
        "params": {"code_1": "HIGH_CPU"},
    },
    "timeframeInSeconds": 86400,
    "timeUnit": "hours",
    "groupingCriteria": ["labels.host"],
    "requireApprove": False,
    "resolveOn": "never",
    "createOn": "any",
    "threshold": 1,
    "incidentNameTemplate": "{{ alert.labels.code }} on {{ alert.labels.host }}",
    "incidentPrefix": "INC",
}


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_onboarding_wizard_api_journey(db_session, client, test_app):
    headers = {"x-api-key": "some-key"}

    create_code = client.post(
        "/alert-catalog",
        headers=headers,
        json={
            "code": "HIGH_CPU",
            "name": "High CPU",
            "description": "Host CPU is above the warning threshold.",
            "auto_run_on": "none",
        },
    )
    assert create_code.status_code == 200, create_code.text
    entry = create_code.json()
    assert entry["code"] == "HIGH_CPU"
    entry_id = entry["id"]

    create_rule = client.post("/rules", headers=headers, json=CORRELATION_PAYLOAD)
    assert create_rule.status_code == 200, create_rule.text
    rule = create_rule.json()
    assert "HIGH_CPU" in rule["definition_cel"]
    assert rule["grouping_criteria"] == ["labels.host"]

    workflow = Workflow(
        id="onboarding-notify-high-cpu",
        tenant_id=SINGLE_TENANT_UUID,
        name="Notify on HIGH_CPU",
        description="setup wizard",
        created_by="test",
        interval=None,
        workflow_raw=ONBOARDING_WORKFLOW_YAML,
        is_deleted=False,
        is_disabled=False,
    )
    db_session.add(workflow)
    db_session.commit()

    attach = client.put(
        f"/alert-catalog/{entry_id}",
        headers=headers,
        json={
            "code": "HIGH_CPU",
            "name": "High CPU",
            "description": "Host CPU is above the warning threshold.",
            "keep_workflow_id": "onboarding-notify-high-cpu",
            "auto_run_on": "both",
        },
    )
    assert attach.status_code == 200, attach.text
    attached = attach.json()
    assert attached["keep_workflow_id"] == "onboarding-notify-high-cpu"
    assert attached["auto_run_on"] == "both"

    listed = client.get("/alert-catalog", headers=headers)
    assert listed.status_code == 200
    assert listed.json()[0]["keep_workflow_id"] == "onboarding-notify-high-cpu"

    rules = client.get("/rules", headers=headers)
    assert rules.status_code == 200
    assert any("HIGH_CPU" in item["definition_cel"] for item in rules.json())

    paused = client.put(
        f"/alert-catalog/{entry_id}",
        headers=headers,
        json={
            "code": "HIGH_CPU",
            "name": "High CPU",
            "description": "Host CPU is above the warning threshold.",
            "keep_workflow_id": "onboarding-notify-high-cpu",
            "auto_run_on": "both",
            "disabled": True,
        },
    )
    assert paused.status_code == 200, paused.text
    assert paused.json()["disabled"] is True

    deleted = client.delete(f"/alert-catalog/{entry_id}", headers=headers)
    assert deleted.status_code == 200, deleted.text
    deleted_rule = client.delete(f"/rules/{rule['id']}", headers=headers)
    assert deleted_rule.status_code == 200, deleted_rule.text
    remaining = client.get("/alert-catalog", headers=headers)
    assert remaining.status_code == 200
    assert remaining.json() == []
