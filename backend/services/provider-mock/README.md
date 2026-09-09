# Keep Provider Mock
#
# Local mock for Grafana, Mimir Alertmanager (Keep type: prometheus), and
# VictoriaMetrics. Use it to register providers into Keep and fire webhook
# events while validating end-to-end alert ingestion.
#
# Quick start (Docker only — do not run on the host):
#
#   make mock-providers
#   open http://localhost:8099
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
# UI workflow
# -----------
# Alert sources tab:
# 1. Confirm Keep API URL + API key.
# 2. Click Register on Grafana / Mimir Alertmanager / VictoriaMetrics.
# 3. Click Send event (firing or resolved). Confirm the alert in Keep UI.
#
# Temporal tab:
# 1. Ensure `make deps` (or docker-compose.temporal.yml) is up.
# 2. Confirm address localhost:7233 / namespace default.
# 3. Click Register Temporal. Confirm mock-temporal in Keep Providers.
#
# Tests (containerized):
#
#   make mock-providers-test
