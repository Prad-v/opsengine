from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.db.provider import Provider
from tests.fixtures.client import client, setup_api_key, test_app  # noqa


def _seed_temporal_provider(db_session, provider_id="mock-temporal"):
    existing = db_session.get(Provider, provider_id)
    if existing:
        return existing
    provider = Provider(
        id=provider_id,
        tenant_id=SINGLE_TENANT_UUID,
        name="mock-temporal",
        description="Mock Temporal",
        type="temporal",
        installed_by="test",
        installation_time=datetime.now(tz=timezone.utc),
        configuration_key=f"provider_{provider_id}",
        validatedScopes={"connect": True},
        consumer=False,
        pulling_enabled=False,
        last_pull_time=None,
        provider_metadata={},
    )
    db_session.add(provider)
    db_session.commit()
    return provider


def _check_payload(provider_id="mock-temporal", check_key="public-api"):
    return {
        "check_key": check_key,
        "name": "Public API",
        "description": "HTTP health",
        "prober": "http",
        "module_config": {"valid_status_codes": [200], "timeout_seconds": 5},
        "targets": ["https://example.com/health"],
        "interval_seconds": 60,
        "labels": {"service": "api"},
        "task_queue": "keep-synth",
        "temporal_provider_id": provider_id,
        "enabled": True,
    }


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_synthetic_checks_crud(db_session, client, test_app):
    _seed_temporal_provider(db_session)
    mock_provider = MagicMock()
    mock_provider.upsert_interval_schedule.return_value = {
        "schedule_id": "synth-check-public-api",
        "action": "created",
    }
    mock_provider.delete_schedule.return_value = {
        "schedule_id": "synth-check-public-api",
        "action": "deleted",
    }

    with patch(
        "keep.api.routes.synthetic_checks._get_temporal_provider",
        return_value=mock_provider,
    ):
        create_resp = client.post(
            "/synthetic-checks",
            headers={"x-api-key": "some-key"},
            json=_check_payload(),
        )
    assert create_resp.status_code == 200, create_resp.text
    created = create_resp.json()
    assert created["check_key"] == "public-api"
    assert created["prober"] == "http"
    assert created["schedule_id"] == "synth-check-public-api"
    assert created["provider_name"] == "mock-temporal"
    entry_id = created["id"]
    mock_provider.upsert_interval_schedule.assert_called()

    list_resp = client.get(
        "/synthetic-checks",
        headers={"x-api-key": "some-key"},
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    get_resp = client.get(
        f"/synthetic-checks/{entry_id}",
        headers={"x-api-key": "some-key"},
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Public API"

    with patch(
        "keep.api.routes.synthetic_checks._get_temporal_provider",
        return_value=mock_provider,
    ):
        update_resp = client.put(
            f"/synthetic-checks/{entry_id}",
            headers={"x-api-key": "some-key"},
            json={
                **_check_payload(),
                "name": "Public API v2",
                "interval_seconds": 120,
                "prober": "tcp",
                "targets": ["example.com:443"],
            },
        )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Public API v2"
    assert update_resp.json()["interval_seconds"] == 120
    assert update_resp.json()["prober"] == "tcp"

    with patch(
        "keep.api.routes.synthetic_checks._get_temporal_provider",
        return_value=mock_provider,
    ):
        delete_resp = client.delete(
            f"/synthetic-checks/{entry_id}",
            headers={"x-api-key": "some-key"},
        )
    assert delete_resp.status_code == 200
    mock_provider.delete_schedule.assert_called()

    list_after = client.get(
        "/synthetic-checks",
        headers={"x-api-key": "some-key"},
    )
    assert list_after.status_code == 200
    assert list_after.json() == []


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_synthetic_checks_rejects_bad_prober(db_session, client, test_app):
    _seed_temporal_provider(db_session)
    with patch(
        "keep.api.routes.synthetic_checks._get_temporal_provider",
        return_value=MagicMock(),
    ):
        resp = client.post(
            "/synthetic-checks",
            headers={"x-api-key": "some-key"},
            json={**_check_payload(), "prober": "icmp"},
        )
    assert resp.status_code == 422


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_synthetic_checks_run(db_session, client, test_app):
    _seed_temporal_provider(db_session)
    mock_provider = MagicMock()
    mock_provider.upsert_interval_schedule.return_value = {
        "schedule_id": "synth-check-public-api",
        "action": "created",
    }
    mock_provider._run_async.return_value = {
        "workflow_id": "synth-check-public-api-manual-1",
        "run_id": "run-1",
        "task_queue": "keep-synth",
        "workflow_type": "ProbeTargetGroup",
        "namespace": "default",
    }

    with patch(
        "keep.api.routes.synthetic_checks._get_temporal_provider",
        return_value=mock_provider,
    ):
        created = client.post(
            "/synthetic-checks",
            headers={"x-api-key": "some-key"},
            json=_check_payload(),
        ).json()
        run_resp = client.post(
            f"/synthetic-checks/{created['id']}/run",
            headers={"x-api-key": "some-key"},
            json={},
        )
    assert run_resp.status_code == 200, run_resp.text
    body = run_resp.json()
    assert body["workflow_type"] == "ProbeTargetGroup"
    assert body["check_key"] == "public-api"
    mock_provider._run_async.assert_called()
