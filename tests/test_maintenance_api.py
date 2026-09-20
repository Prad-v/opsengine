from datetime import datetime, timedelta, timezone

import pytest

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from tests.fixtures.client import client, setup_api_key, test_app  # noqa

HEADERS = {"x-api-key": "some-key"}


def _payload(**overrides):
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
def test_maintenance_crud_and_actions(db_session, client, test_app):
    missing = client.post("/maintenance", headers=HEADERS, json={"name": "x"})
    assert missing.status_code == 422

    blank_cel = client.post(
        "/maintenance",
        headers=HEADERS,
        json=_payload(cel_query="   "),
    )
    assert blank_cel.status_code == 422

    zero_duration = client.post(
        "/maintenance",
        headers=HEADERS,
        json=_payload(duration_seconds=0),
    )
    assert zero_duration.status_code == 422

    create_resp = client.post("/maintenance", headers=HEADERS, json=_payload())
    assert create_resp.status_code == 200, create_resp.text
    created = create_resp.json()
    assert created["name"] == "gpu-host-maintenance"
    assert created["suppress"] is True
    assert created["priority"] == 0
    assert created["status"] in {"active", "upcoming"}
    start = datetime.fromisoformat(created["start_time"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(created["end_time"].replace("Z", "+00:00"))
    assert int((end - start).total_seconds()) == 300
    rule_id = created["id"]

    omitted_suppress = client.post(
        "/maintenance",
        headers=HEADERS,
        json={
            "name": "default-suppress",
            "cel_query": "true",
            "start_time": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": 60,
        },
    )
    assert omitted_suppress.status_code == 200, omitted_suppress.text
    assert omitted_suppress.json()["suppress"] is True

    listed = client.get("/maintenance", headers=HEADERS)
    assert listed.status_code == 200
    assert len(listed.json()) == 2

    updated = client.put(
        f"/maintenance/{rule_id}",
        headers=HEADERS,
        json=_payload(duration_seconds=600, name="gpu-host-maintenance-v2"),
    )
    assert updated.status_code == 200
    updated_body = updated.json()
    assert updated_body["name"] == "gpu-host-maintenance-v2"
    start = datetime.fromisoformat(updated_body["start_time"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(updated_body["end_time"].replace("Z", "+00:00"))
    assert int((end - start).total_seconds()) == 600

    ended = client.post(f"/maintenance/{rule_id}/end-now", headers=HEADERS)
    assert ended.status_code == 200
    assert ended.json()["enabled"] is False
    assert ended.json()["status"] == "disabled"

    extended = client.post(
        f"/maintenance/{rule_id}/extend",
        headers=HEADERS,
        json={"duration_seconds": 1800},
    )
    assert extended.status_code == 200
    assert extended.json()["enabled"] is True
    assert extended.json()["status"] in {"active", "upcoming"}

    preview = client.post(
        "/maintenance/preview",
        headers=HEADERS,
        json={"cel_query": 'source == "prometheus"'},
    )
    assert preview.status_code == 200
    assert "count" in preview.json()
    assert "sample" in preview.json()

    deleted = client.delete(f"/maintenance/{rule_id}", headers=HEADERS)
    assert deleted.status_code == 200
    remaining = client.get("/maintenance", headers=HEADERS)
    ids = [rule["id"] for rule in remaining.json()]
    assert rule_id not in ids
