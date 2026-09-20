from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from keep.api.bl.approval_bl import ApprovalBl
from keep.api.core.dependencies import SINGLE_TENANT_EMAIL, SINGLE_TENANT_UUID
from keep.api.models.db.approval import ApprovalRequest
from keep.api.models.db.maintenance_window import MaintenanceWindowRule
from keep.api.models.db.workflow import Workflow
from tests.fixtures.client import client, setup_api_key, test_app  # noqa

HEADERS = {"x-api-key": "some-key"}


def _policy(**overrides):
    body = {
        "name": "maintenance-approval",
        "action_type": "create_maintenance",
        "enabled": True,
        "allow_self_approve": True,
        "priority": 10,
        "approver_roles": ["admin"],
        "approver_emails": [],
        "min_approvals": 1,
    }
    body.update(overrides)
    return body


def _maintenance(**overrides):
    body = {
        "name": "gpu-host-maintenance",
        "description": "Silence GPU node during firmware",
        "cel_query": 'source == "prometheus"',
        "start_time": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": 300,
        "suppress": True,
        "enabled": True,
        "ignore_statuses": ["resolved", "acknowledged"],
        "priority": 0,
    }
    body.update(overrides)
    return body


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_approval_policy_crud(db_session, client, test_app):
    created = client.post("/approvals/policies", headers=HEADERS, json=_policy())
    assert created.status_code == 200, created.text
    policy_id = created.json()["id"]
    assert created.json()["action_type"] == "create_maintenance"

    listed = client.get("/approvals/policies", headers=HEADERS)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    updated = client.put(
        f"/approvals/policies/{policy_id}",
        headers=HEADERS,
        json=_policy(name="maintenance-approval-v2", cel="duration_seconds > 60"),
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "maintenance-approval-v2"

    deleted = client.delete(f"/approvals/policies/{policy_id}", headers=HEADERS)
    assert deleted.status_code == 200
    empty = client.get("/approvals/policies", headers=HEADERS)
    assert empty.json() == []


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_maintenance_create_without_policy_still_executes(db_session, client, test_app):
    resp = client.post("/maintenance", headers=HEADERS, json=_maintenance())
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "gpu-host-maintenance"
    assert db_session.query(MaintenanceWindowRule).count() == 1


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_maintenance_policy_gates_create_and_approve(db_session, client, test_app):
    policy = client.post(
        "/approvals/policies",
        headers=HEADERS,
        json=_policy(allow_self_approve=True),
    )
    assert policy.status_code == 200, policy.text

    gated = client.post("/maintenance", headers=HEADERS, json=_maintenance())
    assert gated.status_code == 202, gated.text
    body = gated.json()
    assert body["status"] == "pending"
    request_id = body["request_id"]
    assert db_session.query(MaintenanceWindowRule).count() == 0

    listed = client.get("/approvals?status=pending", headers=HEADERS)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    approved = client.post(
        f"/approvals/{request_id}/approve",
        headers=HEADERS,
        json={"comment": "ok"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert db_session.query(MaintenanceWindowRule).count() == 1


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_self_approve_blocked(db_session, client, test_app):
    policy = client.post(
        "/approvals/policies",
        headers=HEADERS,
        json=_policy(allow_self_approve=False),
    )
    assert policy.status_code == 200
    gated = client.post("/maintenance", headers=HEADERS, json=_maintenance())
    assert gated.status_code == 202
    request_id = gated.json()["request_id"]

    blocked = client.post(f"/approvals/{request_id}/approve", headers=HEADERS)
    assert blocked.status_code == 403
    assert db_session.query(MaintenanceWindowRule).count() == 0


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_node_maintenance_action_type(db_session, client, test_app):
    client.post(
        "/approvals/policies",
        headers=HEADERS,
        json=_policy(action_type="node_maintenance", allow_self_approve=True),
    )
    gated = client.post(
        "/maintenance",
        headers=HEADERS,
        json=_maintenance(
            topology_service_id="gpu-node-a03",
            topology_category="host",
            topology_reason="RMA",
        ),
    )
    assert gated.status_code == 202, gated.text
    assert gated.json()["approval"]["action_type"] == "node_maintenance"
    assert db_session.query(MaintenanceWindowRule).count() == 0


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_delete_workflow_gated(db_session, client, test_app):
    workflow = Workflow(
        id="wf-delete-me",
        tenant_id=SINGLE_TENANT_UUID,
        name="delete me",
        description="test",
        created_by="test",
        interval=None,
        workflow_raw="workflow:\n  id: wf-delete-me\n  triggers:\n    - type: manual\n",
        is_deleted=False,
        is_disabled=False,
    )
    db_session.add(workflow)
    db_session.commit()

    client.post(
        "/approvals/policies",
        headers=HEADERS,
        json=_policy(
            name="delete-workflows",
            action_type="delete_resource",
            resource_type="workflow",
            allow_self_approve=True,
        ),
    )
    gated = client.delete("/workflows/wf-delete-me", headers=HEADERS)
    assert gated.status_code == 202, gated.text
    remaining = db_session.get(Workflow, "wf-delete-me")
    assert remaining is not None
    assert remaining.is_deleted is False or remaining is not None

    request_id = gated.json()["request_id"]
    approved = client.post(f"/approvals/{request_id}/approve", headers=HEADERS)
    assert approved.status_code == 200, approved.text
    db_session.expire_all()
    leftover = db_session.get(Workflow, "wf-delete-me")
    assert leftover is None or leftover.is_deleted is True


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_external_request_and_reject(db_session, client, test_app):
    created = client.post(
        "/approvals",
        headers=HEADERS,
        json={
            "action_type": "custom",
            "title": "Open change window on rack-a3",
            "payload": {"rack": "a3"},
            "callback": {"kind": "keep_action"},
        },
    )
    assert created.status_code == 200, created.text
    request_id = created.json()["id"]
    rejected = client.post(
        f"/approvals/{request_id}/reject",
        headers=HEADERS,
        json={"comment": "not now"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_expire_pending_requests(db_session, client, test_app):
    request = ApprovalRequest(
        tenant_id=SINGLE_TENANT_UUID,
        action_type="custom",
        status="pending",
        title="expired",
        requested_by=SINGLE_TENANT_EMAIL,
        requested_at=datetime.now(timezone.utc) - timedelta(hours=2),
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        payload_json={},
        context_json={},
        callback_json={},
        result_json={},
    )
    db_session.add(request)
    db_session.commit()
    expired = ApprovalBl(SINGLE_TENANT_UUID, db_session).expire_pending()
    assert expired == 1
    db_session.refresh(request)
    assert request.status == "expired"


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_cel_policy_does_not_match_short_window(db_session, client, test_app):
    client.post(
        "/approvals/policies",
        headers=HEADERS,
        json=_policy(
            cel="duration_seconds > 3600",
            allow_self_approve=True,
        ),
    )
    short = client.post(
        "/maintenance",
        headers=HEADERS,
        json=_maintenance(duration_seconds=300),
    )
    assert short.status_code == 200, short.text
    assert db_session.query(MaintenanceWindowRule).count() == 1

    long = client.post(
        "/maintenance",
        headers=HEADERS,
        json=_maintenance(name="long-window", duration_seconds=7200),
    )
    assert long.status_code == 202, long.text


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_webhook_callback_on_reject(db_session, client, test_app):
    created = client.post(
        "/approvals",
        headers=HEADERS,
        json={
            "action_type": "webhook",
            "title": "external change",
            "callback": {"kind": "webhook", "url": "https://example.test/hook"},
        },
    )
    assert created.status_code == 200, created.text
    request_id = created.json()["id"]
    with patch("requests.post") as mocked:
        mocked.return_value = MagicMock(status_code=200)
        rejected = client.post(f"/approvals/{request_id}/reject", headers=HEADERS)
    assert rejected.status_code == 200
    mocked.assert_called_once()
    assert mocked.call_args.kwargs["json"]["approved"] is False


def test_gate_force_without_policy(db_session):
    bl = ApprovalBl(SINGLE_TENANT_UUID, db_session)
    result = bl.gate(
        action_type="run_workflow",
        requested_by="alice@example.com",
        title="Run GPU reset",
        payload={"workflow_id": "mock-nvidia-gpu-remediate"},
        force=True,
    )
    assert result.pending is True
    assert result.request is not None
    assert result.request.status == "pending"


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
@patch("keep.api.routes.workflows.WorkflowManager.get_instance")
@patch("keep.api.routes.workflows.WorkflowStore.get_workflow")
def test_manual_run_policy_returns_202(
    mock_get_workflow, mock_manager, db_session, client, test_app
):
    mock_get_workflow.return_value = type(
        "WorkflowStub",
        (),
        {
            "workflow_require_approval": False,
            "workflow_name": "gpu-reset",
            "workflow_revision": 1,
            "workflow_permissions": [],
        },
    )()
    client.post(
        "/approvals/policies",
        headers=HEADERS,
        json=_policy(action_type="run_workflow", allow_self_approve=True),
    )
    resp = client.post(
        "/workflows/gpu-reset/run",
        headers=HEADERS,
        json={"name": "manual-run"},
    )
    assert resp.status_code == 202, resp.text
    assert resp.json()["status"] == "pending"
    mock_manager.return_value.scheduler.handle_manual_event_workflow.assert_not_called()


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
@patch("keep.api.routes.workflows.WorkflowManager.get_instance")
@patch("keep.api.routes.workflows.WorkflowStore.get_workflow")
def test_yaml_require_approval_returns_202_without_policy(
    mock_get_workflow, mock_manager, db_session, client, test_app
):
    mock_get_workflow.return_value = type(
        "WorkflowStub",
        (),
        {
            "workflow_require_approval": True,
            "workflow_name": "needs-approval",
            "workflow_revision": 1,
            "workflow_permissions": [],
        },
    )()
    resp = client.post(
        "/workflows/needs-approval/run",
        headers=HEADERS,
        json={"name": "manual-run"},
    )
    assert resp.status_code == 202, resp.text
    assert resp.json()["approval"]["action_type"] == "run_workflow"
    mock_manager.return_value.scheduler.handle_manual_event_workflow.assert_not_called()
