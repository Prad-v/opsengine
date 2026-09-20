from unittest.mock import MagicMock, patch

import pytest

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.db.workflow import Workflow
from tests.fixtures.client import client, setup_api_key, test_app  # noqa


def _seed_workflow(db_session, workflow_id="mock-nvidia-gpu-remediate"):
    existing = db_session.get(Workflow, workflow_id)
    if existing:
        return existing
    workflow = Workflow(
        id=workflow_id,
        tenant_id=SINGLE_TENANT_UUID,
        name="GPU remediate",
        description="test",
        created_by="test",
        interval=None,
        workflow_raw="workflow:\n  id: mock-nvidia-gpu-remediate\n  triggers:\n    - type: manual\n",
        is_deleted=False,
        is_disabled=False,
    )
    db_session.add(workflow)
    db_session.commit()
    return workflow


def _payload(**overrides):
    body = {
        "code": "nvidia_gpu_thermal",
        "name": "NVIDIA GPU thermal",
        "description": "Reset GPU when DCGM temp exceeds threshold",
        "runbook_url": "https://wiki.example/gpu-thermal",
        "keep_workflow_id": "mock-nvidia-gpu-remediate",
        "auto_run_on": "both",
        "disabled": False,
    }
    body.update(overrides)
    return body


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_alert_catalog_crud(db_session, client, test_app):
    _seed_workflow(db_session)

    create_resp = client.post(
        "/alert-catalog",
        headers={"x-api-key": "some-key"},
        json=_payload(),
    )
    assert create_resp.status_code == 200, create_resp.text
    created = create_resp.json()
    assert created["code"] == "NVIDIA_GPU_THERMAL"
    assert created["keep_workflow_id"] == "mock-nvidia-gpu-remediate"
    assert created["auto_run_on"] == "both"
    entry_id = created["id"]

    list_resp = client.get("/alert-catalog", headers={"x-api-key": "some-key"})
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    get_resp = client.get(
        f"/alert-catalog/{entry_id}", headers={"x-api-key": "some-key"}
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["runbook_url"] == "https://wiki.example/gpu-thermal"

    update_resp = client.put(
        f"/alert-catalog/{entry_id}",
        headers={"x-api-key": "some-key"},
        json=_payload(auto_run_on="alert", name="GPU thermal v2"),
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["auto_run_on"] == "alert"
    assert update_resp.json()["name"] == "GPU thermal v2"

    dup = client.post(
        "/alert-catalog",
        headers={"x-api-key": "some-key"},
        json=_payload(),
    )
    assert dup.status_code == 409

    missing_wf = client.post(
        "/alert-catalog",
        headers={"x-api-key": "some-key"},
        json=_payload(code="HIGH_CPU", keep_workflow_id="does-not-exist"),
    )
    assert missing_wf.status_code == 400

    delete_resp = client.delete(
        f"/alert-catalog/{entry_id}", headers={"x-api-key": "some-key"}
    )
    assert delete_resp.status_code == 200
    empty = client.get("/alert-catalog", headers={"x-api-key": "some-key"})
    assert empty.json() == []


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_alert_catalog_rejects_invalid_auto_run(db_session, client, test_app):
    resp = client.post(
        "/alert-catalog",
        headers={"x-api-key": "some-key"},
        json=_payload(keep_workflow_id=None, auto_run_on="whenever"),
    )
    assert resp.status_code == 422


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_enhance_description_requires_ai(db_session, client, test_app):
    with patch(
        "keep.api.routes.alert_catalog.get_openai_client_for_tenant",
        return_value=(None, None, {"configured": False}),
    ):
        resp = client.post(
            "/alert-catalog/enhance-description",
            headers={"x-api-key": "some-key"},
            json={"code": "NVIDIA_GPU_THERMAL", "description": "gpu hot"},
        )
    assert resp.status_code == 400
    assert "Settings" in resp.json()["detail"]


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_enhance_description_uses_tenant_ai(db_session, client, test_app):
    completion = MagicMock()
    completion.choices = [
        MagicMock(
            message=MagicMock(
                content=(
                    "NVIDIA_GPU_THERMAL fires when GPU temperature exceeds "
                    "the DCGM threshold. Reset the GPU and page on-call."
                )
            )
        )
    ]
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = completion

    with patch(
        "keep.api.routes.alert_catalog.get_openai_client_for_tenant",
        return_value=(mock_client, "gpt-4o-mini", {"configured": True}),
    ):
        resp = client.post(
            "/alert-catalog/enhance-description",
            headers={"x-api-key": "some-key"},
            json={
                "code": "NVIDIA_GPU_THERMAL",
                "name": "NVIDIA GPU thermal",
                "description": "gpu going high",
            },
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "NVIDIA_GPU_THERMAL" in body["description"]
    assert body["model"] == "gpt-4o-mini"
    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "gpt-4o-mini"
    user_msg = kwargs["messages"][1]["content"]
    assert "gpu going high" in user_msg
    assert "NVIDIA_GPU_THERMAL" in user_msg
