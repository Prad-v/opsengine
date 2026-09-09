"""
Chronosphere Provider receives Alert Manager webhook notifications from
Chronosphere Observability Platform.

Payload format is Prometheus Alertmanager-compatible. See:
https://docs.chronosphere.io/investigate/alerts/notifications/notifiers/webhook
"""

from __future__ import annotations

import dataclasses
import datetime
import hashlib
import hmac
import json
import time
from typing import Optional

import pydantic

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class ChronosphereProviderAuthConfig:
    """Optional Chronosphere webhook signing key for HMAC verification."""

    signing_key: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": (
                "Chronosphere Webhook Signing Key (from My Account). "
                "When set, Keep verifies Chronosphere-Webhook-Signature-V1 on inbound webhooks."
            ),
            "sensitive": True,
            "hint": "SysAdmin role required to view the signing key in Chronosphere",
        },
    )


class ChronosphereProvider(BaseProvider):
    """Get alerts from Chronosphere Alert Manager into Keep via webhooks."""

    PROVIDER_DISPLAY_NAME = "Chronosphere"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert"]
    provider_description = (
        "Receive Chronosphere Alert Manager webhook notifications "
        "(Prometheus Alertmanager-compatible payload)."
    )

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To send alerts from Chronosphere Alert Manager to Keep:

1. In Chronosphere, open **Alerting > Notifiers** and click **Create notifier**.
2. Select **Webhook** as the notifier type.
3. Set the URL to `{keep_webhook_api_url_with_auth}` (includes Keep API key as basic auth).
   Alternatively use URL `{keep_webhook_api_url}?api_key={api_key}` if basic auth is not supported.
4. Optional: enable **Notify when resolved** so resolved alerts are sent to Keep.
5. Save the notifier and attach it to a notification policy / monitor.

Chronosphere also supports configuring the notifier with Chronoctl, Terraform, or API.
See [Chronosphere webhook notifiers](https://docs.chronosphere.io/investigate/alerts/notifications/notifiers/webhook).

**Authentication options in Chronosphere**
- Basic auth: username `keep`, password `{api_key}` (or use the URL with embedded credentials above)
- Bearer token: `{api_key}`

**HMAC webhook signatures (recommended)**
1. In Chronosphere, copy your **Webhook Signing Key** (My Account → Webhook Signing Key).
2. Install/configure this Chronosphere provider in Keep and paste the key into **signing_key**.
3. Use the webhook URL that includes `provider_id` (shown above) so Keep can load the key.
4. Keep verifies `Chronosphere-Webhook-Timestamp` + `Chronosphere-Webhook-Signature-V1`
   (HMAC-SHA256 over `v1:<timestamp>:<raw_body>`) and rejects invalid or stale requests.
"""

    SEVERITIES_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "error": AlertSeverity.HIGH,
        "high": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "medium": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "low": AlertSeverity.LOW,
    }

    STATUS_MAP = {
        "firing": AlertStatus.FIRING,
        "resolved": AlertStatus.RESOLVED,
    }

    FINGERPRINT_FIELDS = ["fingerprint"]

    # Chronosphere recommends 5–15 minutes tolerance for webhook timestamps.
    WEBHOOK_TIMESTAMP_MAX_AGE_SECONDS = 15 * 60

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """Validate Chronosphere provider configuration."""
        self.authentication_config = ChronosphereProviderAuthConfig(
            **(self.config.authentication or {})
        )

    def dispose(self):
        """Nothing to dispose for webhook-only provider."""
        pass

    @staticmethod
    def verify_webhook_signature(
        raw_body: bytes | str,
        timestamp: str,
        signature_header: str,
        signing_key: str,
        max_age_seconds: int = WEBHOOK_TIMESTAMP_MAX_AGE_SECONDS,
        now: Optional[int] = None,
    ) -> bool:
        """
        Verify Chronosphere webhook HMAC-SHA256 signature.

        payload = "v1:" + timestamp + ":" + request_body
        signature = hex(HMAC-SHA256(payload, signing_key))

        The Signature-V1 header may contain multiple comma-separated hex digests
        (with a trailing comma). Any matching signature is accepted.
        """
        if not timestamp or not signature_header or not signing_key:
            return False

        try:
            timestamp_int = int(timestamp)
        except (TypeError, ValueError):
            return False

        current = int(now if now is not None else time.time())
        if abs(current - timestamp_int) > max_age_seconds:
            return False

        if isinstance(raw_body, bytes):
            body_str = raw_body.decode("utf-8")
        else:
            body_str = raw_body

        payload = f"v1:{timestamp}:{body_str}"
        expected = hmac.new(
            signing_key.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        for candidate in signature_header.split(","):
            candidate = candidate.strip()
            if not candidate:
                continue
            if hmac.compare_digest(candidate, expected):
                return True
        return False

    @classmethod
    def _collect_signing_keys(
        cls,
        *,
        tenant_id: str | None,
        provider_id: str | None,
        provider_instance: "BaseProvider | None",
    ) -> list[str]:
        """Resolve Chronosphere signing keys from the installed provider config(s)."""
        keys: list[str] = []

        def _append_key(key: Optional[str]):
            if key and key not in keys:
                keys.append(key)

        if provider_instance is not None:
            auth = getattr(provider_instance, "authentication_config", None)
            _append_key(getattr(auth, "signing_key", None))
            return keys

        if not tenant_id:
            return keys

        # Lazy import to avoid circular imports at module load.
        from keep.providers.providers_factory import ProvidersFactory

        if provider_id:
            try:
                instance = ProvidersFactory.get_installed_provider(
                    tenant_id=tenant_id,
                    provider_id=provider_id,
                    provider_type="chronosphere",
                )
                auth = getattr(instance, "authentication_config", None)
                _append_key(getattr(auth, "signing_key", None))
            except Exception:
                pass
            return keys

        try:
            for installed in ProvidersFactory.get_installed_providers(
                tenant_id, include_details=True
            ):
                if installed.type != "chronosphere":
                    continue
                details = installed.details or {}
                authentication = details.get("authentication") or {}
                if isinstance(authentication, dict):
                    _append_key(authentication.get("signing_key"))
                # Some secrets store auth fields at the top level.
                _append_key(details.get("signing_key"))
        except Exception:
            pass

        return keys

    @classmethod
    def verify_webhook_authentication(
        cls,
        headers: dict | None,
        raw_body: bytes,
        *,
        tenant_id: str | None = None,
        provider_id: str | None = None,
        provider_instance: "BaseProvider | None" = None,
    ) -> None:
        """
        Verify Chronosphere HMAC webhook signatures when a signing_key is configured.

        If no signing key is configured for this tenant/provider, verification is skipped
        (Keep API-key auth still applies). When a key is present, missing/invalid/stale
        signatures cause the request to be rejected.
        """
        signing_keys = cls._collect_signing_keys(
            tenant_id=tenant_id,
            provider_id=provider_id,
            provider_instance=provider_instance,
        )
        if not signing_keys:
            return

        header_map = headers or {}

        def _header(name: str) -> str:
            # Starlette Headers.get is case-insensitive; plain dicts are not.
            if hasattr(header_map, "get"):
                value = header_map.get(name)
                if value:
                    return str(value)
            lower_name = name.lower()
            try:
                items = header_map.items()
            except Exception:
                return ""
            for key, value in items:
                if str(key).lower() == lower_name and value:
                    return str(value)
            return ""

        timestamp = _header("Chronosphere-Webhook-Timestamp")
        signature = _header("Chronosphere-Webhook-Signature-V1")

        if not timestamp or not signature:
            raise ProviderException(
                "Missing Chronosphere webhook signature headers "
                "(Chronosphere-Webhook-Timestamp / Chronosphere-Webhook-Signature-V1)"
            )

        if isinstance(raw_body, str):
            raw_body_bytes = raw_body.encode("utf-8")
        else:
            raw_body_bytes = raw_body or b""

        for signing_key in signing_keys:
            if cls.verify_webhook_signature(
                raw_body=raw_body_bytes,
                timestamp=timestamp,
                signature_header=signature,
                signing_key=signing_key,
            ):
                return

        raise ProviderException("Invalid Chronosphere webhook signature")

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> list[AlertDto]:
        """
        Format Chronosphere Alert Manager webhook payload into Keep alerts.

        Expected shape (Alertmanager-compatible):
        {
          "notifier": "...",
          "status": "firing"|"resolved",
          "alerts": [{ "status", "labels", "annotations", "startsAt", "endsAt", "fingerprint" }],
          "groupLabels": {...},
          "commonLabels": {...},
          "commonAnnotations": {...},
          "version": "4"
        }
        """
        if isinstance(event, list):
            return event

        alerts = event.get("alerts", [event])
        notifier = event.get("notifier")
        common_labels = event.get("commonLabels") or {}
        common_annotations = event.get("commonAnnotations") or {}
        group_labels = event.get("groupLabels") or {}

        alert_dtos: list[AlertDto] = []
        for alert in alerts:
            labels = {
                k.lower(): v for k, v in dict(alert.get("labels") or {}).items()
            }
            annotations = {
                k.lower(): v for k, v in dict(alert.get("annotations") or {}).items()
            }

            alert_name = labels.get("alertname") or alert.get("fingerprint") or "chronosphere-alert"
            description = (
                annotations.pop("description", None)
                or annotations.get("summary")
                or alert_name
            )
            service = labels.get("service") or annotations.get("service")

            status_raw = alert.get("status") or event.get("status")
            status = ChronosphereProvider.STATUS_MAP.get(
                status_raw, AlertStatus.FIRING
            )
            severity = ChronosphereProvider.SEVERITIES_MAP.get(
                str(labels.get("severity", "")).lower(), AlertSeverity.INFO
            )

            starts_at = alert.get("startsAt")
            last_received = starts_at
            if not last_received:
                last_received = datetime.datetime.now(
                    tz=datetime.timezone.utc
                ).isoformat()

            fingerprint = alert.get("fingerprint")

            alert_dto = AlertDto(
                id=fingerprint or alert_name,
                name=alert_name,
                description=description,
                status=status,
                severity=severity,
                service=service,
                lastReceived=last_received,
                startedAt=starts_at,
                environment=labels.pop("environment", "unknown"),
                source=["chronosphere"],
                labels=labels,
                annotations=annotations,
                fingerprint=fingerprint,
                notifier=notifier,
                groupLabels=group_labels,
                commonLabels=common_labels,
                commonAnnotations=common_annotations,
                monitor_slug=annotations.get("monitor_slug"),
                notification_policy_slug=annotations.get("notification_policy_slug"),
                ruleid=annotations.get("ruleid"),
                url=alert.get("generatorURL"),
                payload=alert,
            )

            for label_key, label_value in labels.items():
                if getattr(alert_dto, label_key, None) is not None:
                    continue
                setattr(alert_dto, label_key, label_value)

            for field in ("value", "instance", "job"):
                if getattr(alert_dto, field, None) is None:
                    setattr(alert_dto, field, "")

            alert_dtos.append(alert_dto)

        return alert_dtos

    @classmethod
    def simulate_alert(cls, **kwargs) -> dict:
        """Mock a Chronosphere Alert Manager webhook payload."""
        import random

        from keep.providers.chronosphere_provider.alerts_mock import ALERTS

        alert_type = kwargs.get("alert_type") or random.choice(list(ALERTS.keys()))
        to_wrap_with_provider_type = kwargs.get("to_wrap_with_provider_type")

        alert_payload = json.loads(json.dumps(ALERTS[alert_type]["payload"]))
        alert_parameters = ALERTS[alert_type].get("parameters", {})

        for parameter, parameter_options in alert_parameters.items():
            if "." in parameter:
                parts = parameter.split(".")
                if parts[0] not in alert_payload:
                    alert_payload[parts[0]] = {}
                alert_payload[parts[0]][parts[1]] = random.choice(parameter_options)
            else:
                alert_payload[parameter] = random.choice(parameter_options)

        alert_payload["labels"]["alertname"] = alert_type
        alert_payload["status"] = random.choice(
            [AlertStatus.FIRING.value, AlertStatus.RESOLVED.value]
        )
        alert_payload["startsAt"] = datetime.datetime.now(
            tz=datetime.timezone.utc
        ).isoformat()
        alert_payload["endsAt"] = "0001-01-01T00:00:00Z"

        fingerprint_src = json.dumps(alert_payload["labels"], sort_keys=True)
        alert_payload["fingerprint"] = hashlib.md5(
            fingerprint_src.encode()
        ).hexdigest()

        event = {
            "notifier": "keep-webhook",
            "status": alert_payload["status"],
            "alerts": [alert_payload],
            "groupLabels": {
                "alertname": alert_type,
                "severity": alert_payload["labels"].get("severity", "critical"),
            },
            "commonLabels": alert_payload["labels"],
            "commonAnnotations": alert_payload.get("annotations", {}),
            "version": "4",
        }

        if to_wrap_with_provider_type:
            return {"keep_source_type": "chronosphere", "event": event}
        return event


if __name__ == "__main__":
    pass
