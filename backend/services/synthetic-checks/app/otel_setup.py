"""OpenTelemetry metrics setup for synthetic checks."""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_meter = None
_probe_success = None
_probe_duration = None


def setup_otel() -> None:
    global _meter, _probe_success, _probe_duration

    metrics_enabled = os.environ.get("METRIC_OTEL_ENABLED", "").lower() == "true"
    endpoint = os.environ.get(
        "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT"
    ) or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")

    if not metrics_enabled or not endpoint:
        logger.info(
            "OTEL metrics disabled (set METRIC_OTEL_ENABLED=true and OTEL_EXPORTER_OTLP_* )"
        )
        return

    try:
        from opentelemetry import metrics
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
            OTLPMetricExporter,
        )
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.semconv.resource import ResourceAttributes
    except ImportError:
        logger.warning("OpenTelemetry packages not installed; metrics disabled")
        return

    service_name = os.environ.get("OTEL_SERVICE_NAME", "synthetic-checks")
    resource = Resource.create(
        {ResourceAttributes.SERVICE_NAME: service_name}
    )
    # grpc exporter expects host:port without scheme in some versions; pass as-is.
    exporter = OTLPMetricExporter(endpoint=endpoint, insecure=True)
    reader = PeriodicExportingMetricReader(exporter)
    provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(provider)
    _meter = metrics.get_meter("synthetic-checks")
    _probe_success = _meter.create_gauge(
        name="probe_success",
        description="Synthetic probe success (1) or failure (0)",
        unit="1",
    )
    _probe_duration = _meter.create_gauge(
        name="probe_duration_seconds",
        description="Synthetic probe duration in seconds",
        unit="s",
    )
    logger.info("OTEL metrics enabled endpoint=%s service=%s", endpoint, service_name)


def record_probe_metrics(
    *,
    success: bool,
    duration_seconds: float,
    target: str,
    prober: str,
    check_key: str | None = None,
    labels: dict[str, Any] | None = None,
) -> None:
    if _probe_success is None or _probe_duration is None:
        return

    attrs: dict[str, str] = {
        "job": "synthetic-checks",
        "instance": target,
        "prober": prober,
        "module": prober,
        "check_key": check_key or "manual",
    }
    if labels:
        for key, value in labels.items():
            if value is None:
                continue
            attrs[str(key)] = str(value)

    _probe_success.set(1 if success else 0, attrs)
    _probe_duration.set(float(duration_seconds), attrs)
