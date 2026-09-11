from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.db.provider import Provider
from keep.api.models.db.temporal_workflow_catalog import TemporalWorkflowCatalog
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


def _catalog_payload(provider_id="mock-temporal", catalog_key="remediate-incident"):
    return {
        "catalog_key": catalog_key,
        "name": "Remediate Incident",
        "description": "Start remediation",
        "workflow_type": "RemediateIncident",
        "task_queue": "keep-ops",
        "workflow_id_template": "incident-{{incident.id}}-{{catalog.id}}",
        "input_mapping": {
            "incident_id": "id",
            "name": "name",
        },
        "provider_id": provider_id,
        "disabled": False,
    }


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_temporal_workflows_crud(db_session, client, test_app):
    _seed_temporal_provider(db_session)

    with patch(
        "keep.api.routes.temporal_workflows._get_temporal_provider",
        return_value=MagicMock(),
    ):
        create_resp = client.post(
            "/temporal-workflows",
            headers={"x-api-key": "some-key"},
            json=_catalog_payload(),
        )
    assert create_resp.status_code == 200, create_resp.text
    created = create_resp.json()
    assert created["catalog_key"] == "remediate-incident"
    assert created["workflow_type"] == "RemediateIncident"
    assert created["provider_name"] == "mock-temporal"
    entry_id = created["id"]

    list_resp = client.get(
        "/temporal-workflows",
        headers={"x-api-key": "some-key"},
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    get_resp = client.get(
        f"/temporal-workflows/{entry_id}",
        headers={"x-api-key": "some-key"},
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Remediate Incident"

    with patch(
        "keep.api.routes.temporal_workflows._get_temporal_provider",
        return_value=MagicMock(),
    ):
        update_resp = client.put(
            f"/temporal-workflows/{entry_id}",
            headers={"x-api-key": "some-key"},
            json={
                **_catalog_payload(),
                "name": "Remediate Incident v2",
                "task_queue": "keep-ops-v2",
            },
        )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Remediate Incident v2"
    assert update_resp.json()["task_queue"] == "keep-ops-v2"

    delete_resp = client.delete(
        f"/temporal-workflows/{entry_id}",
        headers={"x-api-key": "some-key"},
    )
    assert delete_resp.status_code == 200

    list_after = client.get(
        "/temporal-workflows",
        headers={"x-api-key": "some-key"},
    )
    assert list_after.status_code == 200
    assert list_after.json() == []


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_temporal_workflows_auto_catalog_key(db_session, client, test_app):
    _seed_temporal_provider(db_session)
    payload = _catalog_payload()
    del payload["catalog_key"]
    del payload["workflow_id_template"]

    with patch(
        "keep.api.routes.temporal_workflows._get_temporal_provider",
        return_value=MagicMock(),
    ):
        resp = client.post(
            "/temporal-workflows",
            headers={"x-api-key": "some-key"},
            json=payload,
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["catalog_key"] == "remediate-incident"
    assert data["workflow_id_template"] == "incident-{{incident.id}}-{{catalog.id}}"

    # Second create with same name gets a unique suffix
    with patch(
        "keep.api.routes.temporal_workflows._get_temporal_provider",
        return_value=MagicMock(),
    ):
        resp2 = client.post(
            "/temporal-workflows",
            headers={"x-api-key": "some-key"},
            json=payload,
        )
    assert resp2.status_code == 200, resp2.text
    assert resp2.json()["catalog_key"] == "remediate-incident-2"


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_temporal_workflows_duplicate_key(db_session, client, test_app):
    _seed_temporal_provider(db_session)
    now = datetime.now(tz=timezone.utc)
    db_session.add(
        TemporalWorkflowCatalog(
            tenant_id=SINGLE_TENANT_UUID,
            catalog_key="remediate-incident",
            name="Existing",
            workflow_type="RemediateIncident",
            task_queue="keep-ops",
            provider_id="mock-temporal",
            created_at=now,
            updated_at=now,
            input_mapping={},
        )
    )
    db_session.commit()

    with patch(
        "keep.api.routes.temporal_workflows._get_temporal_provider",
        return_value=MagicMock(),
    ):
        resp = client.post(
            "/temporal-workflows",
            headers={"x-api-key": "some-key"},
            json=_catalog_payload(),
        )
    assert resp.status_code == 409


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
def test_temporal_workflows_start_for_incident(db_session, client, test_app):
    from keep.api.core.db import create_incident_from_dto
    from keep.api.models.incident import IncidentDtoIn

    _seed_temporal_provider(db_session)
    now = datetime.now(tz=timezone.utc)
    entry = TemporalWorkflowCatalog(
        tenant_id=SINGLE_TENANT_UUID,
        catalog_key="remediate-incident",
        name="Remediate Incident",
        workflow_type="RemediateIncident",
        task_queue="keep-ops",
        provider_id="mock-temporal",
        created_at=now,
        updated_at=now,
        input_mapping={"incident_id": "id"},
        workflow_id_template="incident-{{incident.id}}-{{catalog.id}}",
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)

    incident = create_incident_from_dto(
        SINGLE_TENANT_UUID,
        IncidentDtoIn(user_generated_name="Payments down", user_summary="test"),
    )

    mock_provider = MagicMock()
    mock_provider.start_workflow_from_definition.return_value = {
        "workflow_id": f"incident-{incident.id}-remediate-incident",
        "run_id": "run-123",
        "workflow_type": "RemediateIncident",
        "task_queue": "keep-ops",
        "namespace": "default",
        "catalog_id": "remediate-incident",
        "catalog_name": "Remediate Incident",
    }

    with patch(
        "keep.api.routes.temporal_workflows._get_temporal_provider",
        return_value=mock_provider,
    ):
        resp = client.post(
            f"/temporal-workflows/{entry.id}/start",
            headers={"x-api-key": "some-key"},
            json={"incident_id": str(incident.id)},
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["catalog_id"] == "remediate-incident"
    assert data["run_id"] == "run-123"
    mock_provider.start_workflow_from_definition.assert_called_once()
