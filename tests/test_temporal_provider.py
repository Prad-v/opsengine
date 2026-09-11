"""
Unit tests for Temporal Provider.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.temporal_provider.temporal_provider import TemporalProvider


@pytest.fixture
def context_manager():
    return ContextManager(tenant_id="test_tenant", workflow_id="test_workflow")


@pytest.fixture
def temporal_config():
    return ProviderConfig(
        description="Test Temporal Provider",
        authentication={
            "address": "localhost:7233",
            "namespace": "default",
            "tls": False,
        },
    )


@pytest.fixture
def temporal_provider(context_manager, temporal_config):
    return TemporalProvider(
        context_manager=context_manager,
        provider_id="test_temporal",
        config=temporal_config,
    )


def test_validate_config(temporal_provider):
    assert temporal_provider.authentication_config.address == "localhost:7233"
    assert temporal_provider.authentication_config.namespace == "default"
    assert temporal_provider.authentication_config.tls is False


def test_provider_factory_loads_temporal():
    from keep.providers.providers_factory import ProvidersFactory

    provider_class = ProvidersFactory.get_provider_class("temporal")
    assert provider_class.__name__ == "TemporalProvider"


def test_notify_requires_workflow_type(temporal_provider):
    with pytest.raises(ProviderException, match="workflow_type is required"):
        temporal_provider._notify(task_queue="keep-ops")


def test_notify_requires_task_queue(temporal_provider):
    with pytest.raises(ProviderException, match="task_queue is required"):
        temporal_provider._notify(workflow_type="RemediateIncident")


def test_start_workflow_notify(temporal_provider):
    mock_handle = MagicMock()
    mock_handle.id = "incident-123"
    mock_handle.result_run_id = "run-abc"

    mock_client = MagicMock()
    mock_client.start_workflow = AsyncMock(return_value=mock_handle)

    with patch.object(
        temporal_provider, "_connect", new=AsyncMock(return_value=mock_client)
    ):
        result = temporal_provider._notify(
            workflow_type="RemediateIncident",
            task_queue="keep-ops",
            workflow_id="incident-123",
            arg={"incident_id": "123", "severity": "critical"},
        )

    mock_client.start_workflow.assert_awaited_once()
    call_args = mock_client.start_workflow.await_args
    assert call_args.args[0] == "RemediateIncident"
    assert call_args.args[1] == {"incident_id": "123", "severity": "critical"}
    assert call_args.kwargs["id"] == "incident-123"
    assert call_args.kwargs["task_queue"] == "keep-ops"
    assert result == {
        "workflow_id": "incident-123",
        "run_id": "run-abc",
        "task_queue": "keep-ops",
        "workflow_type": "RemediateIncident",
        "namespace": "default",
    }


def test_start_workflow_with_args_list(temporal_provider):
    mock_handle = MagicMock()
    mock_handle.id = "wf-1"
    mock_handle.result_run_id = "run-1"

    mock_client = MagicMock()
    mock_client.start_workflow = AsyncMock(return_value=mock_handle)

    with patch.object(
        temporal_provider, "_connect", new=AsyncMock(return_value=mock_client)
    ):
        temporal_provider._notify(
            workflow_type="MultiArgWorkflow",
            task_queue="keep-ops",
            args=["a", "b"],
        )

    call_kwargs = mock_client.start_workflow.await_args.kwargs
    assert call_kwargs["args"] == ["a", "b"]
    assert call_kwargs["task_queue"] == "keep-ops"


def test_describe_workflow_query(temporal_provider):
    mock_status = MagicMock()
    mock_status.name = "RUNNING"
    mock_description = MagicMock()
    mock_description.id = "incident-123"
    mock_description.run_id = "run-abc"
    mock_description.workflow_type = MagicMock(name="RemediateIncident")
    mock_description.workflow_type.name = "RemediateIncident"
    mock_description.task_queue = "keep-ops"
    mock_description.status = mock_status
    mock_description.start_time = None
    mock_description.close_time = None

    mock_handle = MagicMock()
    mock_handle.describe = AsyncMock(return_value=mock_description)

    mock_client = MagicMock()
    mock_client.get_workflow_handle.return_value = mock_handle

    with patch.object(
        temporal_provider, "_connect", new=AsyncMock(return_value=mock_client)
    ):
        result = temporal_provider._query(
            operation="describe_workflow",
            workflow_id="incident-123",
        )

    mock_client.get_workflow_handle.assert_called_once_with(
        "incident-123", run_id=None
    )
    assert result["workflow_id"] == "incident-123"
    assert result["status"] == "RUNNING"
    assert result["workflow_type"] == "RemediateIncident"


def test_signal_workflow(temporal_provider):
    mock_handle = MagicMock()
    mock_handle.signal = AsyncMock()

    mock_client = MagicMock()
    mock_client.get_workflow_handle.return_value = mock_handle

    with patch.object(
        temporal_provider, "_connect", new=AsyncMock(return_value=mock_client)
    ):
        result = temporal_provider._notify(
            operation="signal_workflow",
            workflow_id="incident-123",
            signal_name="approve",
            signal_args={"approved_by": "oncall"},
        )

    mock_handle.signal.assert_awaited_once_with("approve", {"approved_by": "oncall"})
    assert result["status"] == "signaled"


def test_unsupported_operation(temporal_provider):
    with pytest.raises(ProviderException, match="Unsupported Temporal notify"):
        temporal_provider._notify(
            operation="pause_workflow",
            workflow_id="incident-123",
        )


def test_tls_config_with_api_key(context_manager):
    provider = TemporalProvider(
        context_manager=context_manager,
        provider_id="cloud",
        config=ProviderConfig(
            authentication={
                "address": "ns.a1b2c.tmprl.cloud:7233",
                "namespace": "ns.account",
                "api_key": "secret-key",
            }
        ),
    )
    assert provider._build_tls_config(MagicMock) is True


def test_ignores_legacy_workflow_catalog_in_config(context_manager):
    provider = TemporalProvider(
        context_manager=context_manager,
        provider_id="test_temporal",
        config=ProviderConfig(
            authentication={
                "address": "localhost:7233",
                "namespace": "default",
                "workflow_catalog": "[{invalid",
            }
        ),
    )
    assert provider.authentication_config.address == "localhost:7233"


def test_start_workflow_from_definition(context_manager):
    provider = TemporalProvider(
        context_manager=context_manager,
        provider_id="test_temporal",
        config=ProviderConfig(
            authentication={
                "address": "localhost:7233",
                "namespace": "default",
            }
        ),
    )
    entry = {
        "id": "remediate-incident",
        "name": "Remediate Incident",
        "workflow_type": "RemediateIncident",
        "task_queue": "keep-ops",
        "workflow_id_template": "incident-{{incident.id}}-{{catalog.id}}",
        "input_mapping": {
            "incident_id": "id",
            "name": "name",
            "severity": "severity",
        },
    }

    mock_handle = MagicMock()
    mock_handle.id = "incident-abc-remediate-incident"
    mock_handle.result_run_id = "run-1"
    mock_client = MagicMock()
    mock_client.start_workflow = AsyncMock(return_value=mock_handle)

    with patch.object(provider, "_connect", new=AsyncMock(return_value=mock_client)):
        result = provider.start_workflow_from_definition(
            entry,
            incident={
                "id": "abc",
                "name": "Disk full",
                "severity": "critical",
            },
        )

    mock_client.start_workflow.assert_awaited_once()
    call_args = mock_client.start_workflow.await_args
    assert call_args.args[0] == "RemediateIncident"
    assert call_args.args[1] == {
        "incident_id": "abc",
        "name": "Disk full",
        "severity": "critical",
    }
    assert call_args.kwargs["id"] == "incident-abc-remediate-incident"
    assert call_args.kwargs["task_queue"] == "keep-ops"
    assert result["catalog_id"] == "remediate-incident"
    assert result["workflow_id"] == "incident-abc-remediate-incident"
    assert result["incident_id"] == "abc"


def test_start_workflow_from_definition_invalid_entry(temporal_provider):
    with pytest.raises(ProviderException, match="requires id"):
        temporal_provider.start_workflow_from_definition(
            {"name": "Incomplete"},
            incident={"id": "1"},
        )
