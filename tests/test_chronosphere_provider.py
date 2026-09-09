"""
Unit tests for Chronosphere Alert Manager provider.
"""

import hashlib
import hmac
import json
import time

import pytest

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.chronosphere_provider.chronosphere_provider import (
    ChronosphereProvider,
)
from keep.providers.models.provider_config import ProviderConfig


CHRONOSPHERE_WEBHOOK_EVENT = {
    "notifier": "test webhook",
    "status": "firing",
    "alerts": [
        {
            "status": "firing",
            "labels": {
                "alertname": "test alert",
                "component": "remote_write",
                "instance": "localhost:3030",
                "job": "collector_binary",
                "severity": "critical",
                "pod_name": "prom-74cbfb46c9-2ftk9",
            },
            "annotations": {
                "ruleid": "32bb3fbe-c10b-44bb-a4c0-3d053f4a08cd",
                "monitor_slug": "test-monitor",
                "notification_policy_slug": "test-policy",
                "summary": "Remote write is failing",
            },
            "startsAt": "2020-05-19T13:57:21.68227886Z",
            "endsAt": "0001-01-01T00:00:00Z",
            "fingerprint": "7424223989b20025",
        }
    ],
    "groupLabels": {
        "alertname": "test alert",
        "severity": "critical",
    },
    "commonLabels": {
        "alertname": "test alert",
        "component": "remote_write",
        "instance": "localhost:3030",
        "job": "collector_binary",
        "severity": "critical",
        "pod_name": "prom-74cbfb46c9-2ftk9",
    },
    "commonAnnotations": {
        "ruleid": "32bb3fbe-c10b-44bb-a4c0-3d053f4a08cd",
        "monitor_slug": "test-monitor",
        "notification_policy_slug": "test-policy",
    },
    "version": "4",
}


@pytest.fixture
def context_manager():
    return ContextManager(tenant_id="test_tenant", workflow_id="test_workflow")


@pytest.fixture
def chronosphere_provider(context_manager):
    return ChronosphereProvider(
        context_manager=context_manager,
        provider_id="test_chronosphere",
        config=ProviderConfig(
            description="Test Chronosphere Provider",
            authentication={"signing_key": "test-signing-key"},
        ),
    )


def test_provider_factory_loads_chronosphere():
    from keep.providers.providers_factory import ProvidersFactory

    provider_class = ProvidersFactory.get_provider_class("chronosphere")
    assert provider_class.__name__ == "ChronosphereProvider"


def test_validate_config(chronosphere_provider):
    assert chronosphere_provider.authentication_config.signing_key == "test-signing-key"


def test_format_alert_from_chronosphere_webhook():
    alerts = ChronosphereProvider._format_alert(CHRONOSPHERE_WEBHOOK_EVENT)

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.name == "test alert"
    assert alert.status == AlertStatus.FIRING.value
    assert alert.severity == AlertSeverity.CRITICAL.value
    assert alert.fingerprint == "7424223989b20025"
    assert alert.source == ["chronosphere"]
    assert alert.labels["component"] == "remote_write"
    assert alert.monitor_slug == "test-monitor"
    assert alert.notification_policy_slug == "test-policy"
    assert alert.notifier == "test webhook"
    assert alert.instance == "localhost:3030"
    assert alert.job == "collector_binary"
    assert alert.description == "Remote write is failing"


def test_format_alert_resolved_status():
    event = json.loads(json.dumps(CHRONOSPHERE_WEBHOOK_EVENT))
    event["status"] = "resolved"
    event["alerts"][0]["status"] = "resolved"
    event["alerts"][0]["labels"]["severity"] = "warning"

    alerts = ChronosphereProvider._format_alert(event)
    assert alerts[0].status == AlertStatus.RESOLVED.value
    assert alerts[0].severity == AlertSeverity.WARNING.value


def test_format_alert_multiple_alerts():
    event = json.loads(json.dumps(CHRONOSPHERE_WEBHOOK_EVENT))
    second = json.loads(json.dumps(event["alerts"][0]))
    second["fingerprint"] = "aaaaaaaaaaaaaaaa"
    second["labels"]["alertname"] = "second alert"
    second["labels"]["severity"] = "info"
    event["alerts"].append(second)

    alerts = ChronosphereProvider._format_alert(event)
    assert len(alerts) == 2
    assert alerts[1].name == "second alert"
    assert alerts[1].severity == AlertSeverity.INFO.value


def _sign(body: bytes, timestamp: str, key: str) -> str:
    payload = f"v1:{timestamp}:{body.decode('utf-8')}"
    digest = hmac.new(key.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{digest},"


def test_verify_webhook_signature_valid():
    body = json.dumps(CHRONOSPHERE_WEBHOOK_EVENT, separators=(",", ":")).encode()
    timestamp = str(int(time.time()))
    key = "test-signing-key"
    signature = _sign(body, timestamp, key)

    assert ChronosphereProvider.verify_webhook_signature(
        raw_body=body,
        timestamp=timestamp,
        signature_header=signature,
        signing_key=key,
    )


def test_verify_webhook_signature_rejects_bad_signature():
    body = b'{"status":"firing"}'
    timestamp = str(int(time.time()))

    assert not ChronosphereProvider.verify_webhook_signature(
        raw_body=body,
        timestamp=timestamp,
        signature_header="deadbeef,",
        signing_key="test-signing-key",
    )


def test_verify_webhook_signature_rejects_stale_timestamp():
    body = b'{"status":"firing"}'
    key = "test-signing-key"
    stale = str(int(time.time()) - 60 * 60)
    signature = _sign(body, stale, key)

    assert not ChronosphereProvider.verify_webhook_signature(
        raw_body=body,
        timestamp=stale,
        signature_header=signature,
        signing_key=key,
    )


def test_simulate_alert_shape():
    event = ChronosphereProvider.simulate_alert(alert_type="HighCPUUsage")
    assert event["version"] == "4"
    assert event["notifier"] == "keep-webhook"
    assert "alerts" in event
    assert event["alerts"][0]["labels"]["alertname"] == "HighCPUUsage"
    assert "fingerprint" in event["alerts"][0]


def test_verify_webhook_authentication_skips_without_signing_key(context_manager):
    provider = ChronosphereProvider(
        context_manager=context_manager,
        provider_id="test_chronosphere",
        config=ProviderConfig(authentication={}),
    )
    # No signing key configured → no-op (does not raise)
    ChronosphereProvider.verify_webhook_authentication(
        headers={},
        raw_body=b"{}",
        provider_instance=provider,
    )


def test_verify_webhook_authentication_accepts_valid_signature(chronosphere_provider):
    body = json.dumps(CHRONOSPHERE_WEBHOOK_EVENT, separators=(",", ":")).encode()
    timestamp = str(int(time.time()))
    signature = _sign(body, timestamp, "test-signing-key")

    ChronosphereProvider.verify_webhook_authentication(
        headers={
            "Chronosphere-Webhook-Timestamp": timestamp,
            "Chronosphere-Webhook-Signature-V1": signature,
        },
        raw_body=body,
        provider_instance=chronosphere_provider,
    )


def test_verify_webhook_authentication_rejects_missing_headers(chronosphere_provider):
    from keep.exceptions.provider_exception import ProviderException

    with pytest.raises(ProviderException, match="Missing Chronosphere webhook signature"):
        ChronosphereProvider.verify_webhook_authentication(
            headers={},
            raw_body=b'{"status":"firing"}',
            provider_instance=chronosphere_provider,
        )


def test_verify_webhook_authentication_rejects_invalid_signature(chronosphere_provider):
    from keep.exceptions.provider_exception import ProviderException

    body = b'{"status":"firing"}'
    timestamp = str(int(time.time()))

    with pytest.raises(ProviderException, match="Invalid Chronosphere webhook signature"):
        ChronosphereProvider.verify_webhook_authentication(
            headers={
                "Chronosphere-Webhook-Timestamp": timestamp,
                "Chronosphere-Webhook-Signature-V1": "deadbeef,",
            },
            raw_body=body,
            provider_instance=chronosphere_provider,
        )


def test_verify_webhook_authentication_case_insensitive_headers(chronosphere_provider):
    body = b'{"status":"firing"}'
    timestamp = str(int(time.time()))
    signature = _sign(body, timestamp, "test-signing-key")

    ChronosphereProvider.verify_webhook_authentication(
        headers={
            "chronosphere-webhook-timestamp": timestamp,
            "chronosphere-webhook-signature-v1": signature,
        },
        raw_body=body,
        provider_instance=chronosphere_provider,
    )
