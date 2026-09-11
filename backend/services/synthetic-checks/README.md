# Synthetic checks Temporal worker (HTTP/TCP/DNS blackbox probes on keep-synth).
#
# Local (via repo root):
#   docker compose -f docker-compose.temporal.yml up -d --build synthetic-checks
#   # or: make synthetic-checks
#
# Mode 1: Catalog → Synthetic checks (API creates Temporal Schedules)
# Mode 2: Register ProbeTargets in Temporal workflow catalog
#
# Task queue: keep-synth
# Workflows: ProbeTarget, ProbeTargetGroup, ProbeTargets

## Environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `TEMPORAL_ADDRESS` | `temporal:7233` | Temporal frontend |
| `TEMPORAL_NAMESPACE` | `default` | Namespace |
| `TEMPORAL_TASK_QUEUE` | `keep-synth` | Worker queue |
| `KEEP_API_URL` | — | Keep API for alert posting |
| `KEEP_API_KEY` | — | API key with write:alert |
| `METRIC_OTEL_ENABLED` | — | Set `true` to export OTLP metrics |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | — | OTLP collector (e.g. `otel-collector:4317`) |
| `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT` | — | Metrics-only OTLP endpoint |
| `OTEL_SERVICE_NAME` | `synthetic-checks` | Resource service name |
