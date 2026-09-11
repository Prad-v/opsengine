#!/usr/bin/env bash
# Start Keep backend + frontend on the host while Docker deps stay running.
# Invoked by: make start
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BACKEND_PID=""
FRONTEND_PID=""
STOP_DEPS_ON_EXIT="${STOP_DEPS_ON_EXIT:-0}"
API_URL="${API_URL:-http://127.0.0.1:8080}"
VENV_PYTHON="${ROOT_DIR}/.venv/bin/python"
KEEP_API_KEY="${KEEP_API_KEY:-keepappkey}"
AUTO_REGISTER_TEMPORAL_CATALOG="${AUTO_REGISTER_TEMPORAL_CATALOG:-1}"

cleanup() {
  echo ""
  echo "Stopping backend and frontend..."
  if [[ -n "${BACKEND_PID}" ]] && kill -0 "${BACKEND_PID}" 2>/dev/null; then
    kill "${BACKEND_PID}" 2>/dev/null || true
    wait "${BACKEND_PID}" 2>/dev/null || true
  fi
  if [[ -n "${FRONTEND_PID}" ]] && kill -0 "${FRONTEND_PID}" 2>/dev/null; then
    kill "${FRONTEND_PID}" 2>/dev/null || true
    wait "${FRONTEND_PID}" 2>/dev/null || true
  fi
  if [[ "${STOP_DEPS_ON_EXIT}" == "1" ]]; then
    echo "Stopping Docker dependencies..."
    make deps-down || true
  else
    echo "Docker deps left running. Stop everything with: make stop"
  fi
}
trap cleanup EXIT INT TERM

wait_for_api() {
  echo "Waiting for API at ${API_URL}/healthcheck ..."
  for _ in $(seq 1 90); do
    if curl -sf "${API_URL}/healthcheck" >/dev/null 2>&1; then
      echo "API is healthy."
      return 0
    fi
    if ! kill -0 "${BACKEND_PID}" 2>/dev/null; then
      echo "ERROR: backend process exited before becoming healthy."
      return 1
    fi
    sleep 1
  done
  echo "ERROR: timed out waiting for API healthcheck."
  return 1
}

register_temporal_catalogs() {
  if [[ "${AUTO_REGISTER_TEMPORAL_CATALOG}" != "1" ]]; then
    echo "Skipping Temporal catalog registration (AUTO_REGISTER_TEMPORAL_CATALOG=${AUTO_REGISTER_TEMPORAL_CATALOG})."
    return 0
  fi
  if [[ ! -x "${VENV_PYTHON}" ]]; then
    echo "No .venv python; skip Temporal catalog registration."
    return 0
  fi
  echo "Registering Temporal catalog entries (best-effort)..."
  KEEP_API_URL="${API_URL}" KEEP_API_KEY="${KEEP_API_KEY}" \
    "${VENV_PYTHON}" scripts/register_temporal_list_and_zip_catalog.py \
    || echo "ListAndZipDirectory catalog registration skipped (connect Temporal provider first)."
  KEEP_API_URL="${API_URL}" KEEP_API_KEY="${KEEP_API_KEY}" \
    "${VENV_PYTHON}" scripts/register_temporal_probe_targets_catalog.py \
    || echo "ProbeTargets catalog registration skipped (connect Temporal provider first)."
}

echo "Starting Keep API on :8080..."
make backend &
BACKEND_PID=$!

wait_for_api
register_temporal_catalogs

echo "Starting Keep UI on :3000..."
make frontend &
FRONTEND_PID=$!

echo ""
echo "All services started:"
echo "  UI:                http://localhost:3000"
echo "  API:               http://localhost:8080"
echo "  Postgres:          localhost:5432"
echo "  Redis:             localhost:6379"
echo "  Soketi:            localhost:6001"
echo "  Temporal:          localhost:7233 (UI http://localhost:8233)"
echo "  temporal-worker:   keep-ops (ListAndZipDirectory)"
echo "  synthetic-checks:  keep-synth (HTTP/TCP/DNS probes)"
echo "  Catalog UI:        /catalog/synthetic-checks  and  /catalog/temporal-workflows"
echo ""
echo "Press Ctrl+C to stop backend/frontend."
echo "Use 'make stop' to also stop Docker deps."
echo ""

wait -n "${BACKEND_PID}" "${FRONTEND_PID}" || true
wait || true
