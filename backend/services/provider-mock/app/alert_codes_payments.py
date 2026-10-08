"""Reserved payments / disk mock alert codes for Keep catalog + provider-mock setup."""

from __future__ import annotations

from typing import Any

PAYMENTS_ALERT_CODES: tuple[dict[str, Any], ...] = (
    {
        "code": "HIGH_CPU",
        "name": "High CPU",
        "description": "Host CPU above threshold on payments-api.",
        "domain": "infrastructure",
        "role": "capacity_signal",
        "tags": ["payments", "cpu"],
    },
    {
        "code": "HIGH_MEMORY",
        "name": "High memory",
        "description": "Host memory above threshold on payments-api (Grafana or VictoriaMetrics).",
        "domain": "infrastructure",
        "role": "capacity_signal",
        "tags": ["payments", "memory"],
    },
    {
        "code": "DISK_SPACE_LOW",
        "name": "Disk space low",
        "description": "Disk space below threshold (Mimir Alertmanager mock).",
        "domain": "infrastructure",
        "role": "capacity_signal",
        "tags": ["payments", "disk"],
    },
)
