"""Reserved payments / disk mock alert codes for Keep catalog + provider-mock setup."""

from __future__ import annotations

PAYMENTS_ALERT_CODES: tuple[dict[str, str], ...] = (
    {
        "code": "HIGH_CPU",
        "name": "High CPU",
        "description": "Host CPU above threshold on payments-api.",
    },
    {
        "code": "HIGH_MEMORY",
        "name": "High memory",
        "description": "Host memory above threshold on payments-api (Grafana or VictoriaMetrics).",
    },
    {
        "code": "DISK_SPACE_LOW",
        "name": "Disk space low",
        "description": "Disk space below threshold (Mimir Alertmanager mock).",
    },
)
