from datetime import datetime, timezone

import pytest

from keep.api.models.db.maintenance_window import MaintenanceWindowRule
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
def test_no_policy_creates_maintenance_immediately(db_session, client, test_app):
    resp = client.post("/maintenance", headers=HEADERS, json=_maintenance())
    assert resp.status_code == 200, resp.text
    assert db_session.query(MaintenanceWindowRule).count() == 1


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_matching_policy_returns_202_and_does_not_insert(db_session, client, test_app):
    created = client.post(
        "/approvals/policies",
        headers=HEADERS,
        json=_policy(allow_self_approve=True),
    )
    assert created.status_code == 200, created.text
    gated = client.post("/maintenance", headers=HEADERS, json=_maintenance())
    assert gated.status_code == 202, gated.text
    assert gated.json()["status"] == "pending"
    assert db_session.query(MaintenanceWindowRule).count() == 0


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_approve_creates_the_maintenance_rule(db_session, client, test_app):
    client.post(
        "/approvals/policies",
        headers=HEADERS,
        json=_policy(allow_self_approve=True),
    )
    gated = client.post("/maintenance", headers=HEADERS, json=_maintenance())
    request_id = gated.json()["request_id"]
    approved = client.post(
        f"/approvals/{request_id}/approve",
        headers=HEADERS,
        json={"comment": "ok"},
    )
    assert approved.status_code == 200, approved.text
    assert db_session.query(MaintenanceWindowRule).count() == 1


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_self_approve_blocked_leaves_no_rule(db_session, client, test_app):
    client.post(
        "/approvals/policies",
        headers=HEADERS,
        json=_policy(allow_self_approve=False),
    )
    gated = client.post("/maintenance", headers=HEADERS, json=_maintenance())
    request_id = gated.json()["request_id"]
    blocked = client.post(f"/approvals/{request_id}/approve", headers=HEADERS)
    assert blocked.status_code == 403
    assert db_session.query(MaintenanceWindowRule).count() == 0
