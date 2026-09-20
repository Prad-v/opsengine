# Keep Provider Mock
#
# Local mock for Grafana, Mimir Alertmanager (Keep type: prometheus), and
# VictoriaMetrics, plus Compose NetBox for DCIM topology. Use it to register
# providers into Keep and fire webhook events while validating end-to-end
# alert ingestion.
#
# Quick start (Docker only — do not run on the host):
#
#   make start                 # includes provider-mock at :8099 and NetBox at :8000
#   open http://localhost:8099
#   open http://localhost:8000  # admin / admin (first boot 1–2 min)
#
# Restart mock + NetBox:
#
#   make mock-providers
#
# Or:
#
#   docker compose -f backend/services/provider-mock/docker-compose.yml up --build
#
# Environment
# -----------
# KEEP_API_URL      Keep API base URL from inside the mock container
#                   (default: http://host.docker.internal:8080 for hybrid `make start`)
# KEEP_API_KEY      API key with write:providers + write:alert (default: keepappkey)
# PUBLIC_BASE_URL   URL Keep uses to reach this mock during install
#                   (default: http://localhost:8099 for hybrid `make start`)
#
# TEMPORAL_ADDRESS   Temporal frontend as Keep will dial (default: localhost:7233)
# TEMPORAL_NAMESPACE Temporal namespace (default: default)
#
# NETBOX_URL         NetBox as seen from the mock (default: http://netbox:8080)
# KEEP_NETBOX_URL    NetBox as Keep on the host dials (default: http://localhost:8000)
# NETBOX_API_TOKEN   Superuser token (default: 40-hex demo token)
#
# UI workflow
# -----------
# Alert sources tab:
# 1. Confirm Keep API URL + API key.
# 2. Click Register on Grafana / Mimir Alertmanager / VictoriaMetrics.
# 3. Click Send event (firing or resolved). Grafana/Mimir/VM payloads
#    always set reserved labels.code (HIGH_CPU, DISK_SPACE_LOW, HIGH_MEMORY).
# 4. Grafana NVIDIA GPU pack: pick a gpu_* scenario, or use
#    "GPU: rule + temp/mem" / "GPU: rule + all alerts" for AI datacenter demos.
#    NVIDIA GPU server tab: Force fail remediations / emails
#    Synthetic checks tab: fail NVIDIA/AMD inference + training canaries
#    Service Topology tab: push / export / import Keep topology YAML
#    NetBox DCIM: Seed NVIDIA DCIM, then Configure Keep with NetBox
#
# Temporal tab:
# 1. Ensure `make deps` (or docker-compose.temporal.yml) is up.
# 2. Confirm address localhost:7233 / namespace default.
# 3. Click Register Temporal. Confirm mock-temporal in Keep Providers.
#
# Tests (containerized):
#
#   make mock-providers-test
