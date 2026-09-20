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
AUTO_SETUP_NVIDIA_GPU_DEMO="${AUTO_SETUP_NVIDIA_GPU_DEMO:-1}"
AUTO_SETUP_AI_DC_SYNTHETICS="${AUTO_SETUP_AI_DC_SYNTHETICS:-1}"
MOCK_URL="${MOCK_URL:-http://127.0.0.1:8099}"
PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-http://localhost:8099}"
GPU_WORKFLOW_FILE="${GPU_WORKFLOW_FILE:-examples/workflows/mock-nvidia-gpu-remediate.yml}"

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

wait_for_mock() {
  echo "Waiting for provider-mock at ${MOCK_URL}/api/health ..."
  for _ in $(seq 1 30); do
    if curl -sf "${MOCK_URL}/api/health" >/dev/null 2>&1; then
      echo "Provider-mock is healthy."
      return 0
    fi
    sleep 1
  done
  echo "Provider-mock not ready yet (GPU demo provider auto-register may skip)."
  return 1
}

register_mock_provider() {
  local provider="$1"
  curl -sf -X POST "${MOCK_URL}/api/register" \
    -H "Content-Type: application/json" \
    -d "{
      \"provider\": \"${provider}\",
      \"keep_api_url\": \"${API_URL}\",
      \"keep_api_key\": \"${KEEP_API_KEY}\",
      \"public_base_url\": \"${PUBLIC_BASE_URL}\"
    }" >/dev/null
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

setup_nvidia_gpu_demo() {
  if [[ "${AUTO_SETUP_NVIDIA_GPU_DEMO}" != "1" ]]; then
    echo "Skipping NVIDIA GPU demo setup (AUTO_SETUP_NVIDIA_GPU_DEMO=${AUTO_SETUP_NVIDIA_GPU_DEMO})."
    return 0
  fi

  echo "Setting up NVIDIA GPU remediation demo (best-effort)..."

  if wait_for_mock; then
    register_mock_provider temporal \
      && echo "Registered mock-temporal into Keep." \
      || echo "Temporal provider register skipped (may already exist)."
    register_mock_provider grafana \
      && echo "Registered mock-grafana into Keep." \
      || echo "Grafana provider register skipped (may already exist)."
  fi

  if [[ -x "${VENV_PYTHON}" ]]; then
    KEEP_API_URL="${API_URL}" KEEP_API_KEY="${KEEP_API_KEY}" \
      "${VENV_PYTHON}" scripts/register_temporal_nvidia_gpu_catalog.py \
      || echo "RemediateNvidiaGpu catalog registration skipped."
    KEEP_API_URL="${API_URL}" KEEP_API_KEY="${KEEP_API_KEY}" \
      "${VENV_PYTHON}" scripts/register_nvidia_gpu_topology.py \
      || echo "NVIDIA GPU Service Topology seed skipped."
    if [[ "${AUTO_SETUP_AI_DC_SYNTHETICS}" == "1" ]]; then
      KEEP_API_URL="${API_URL}" KEEP_API_KEY="${KEEP_API_KEY}" \
        SYNTH_TARGET_BASE_URL="${SYNTH_TARGET_BASE_URL:-http://host.docker.internal:8099}" \
        "${VENV_PYTHON}" scripts/register_ai_dc_synthetic_checks.py \
        || echo "AI DC synthetic checks seed skipped (connect Temporal + make synthetic-checks)."
    fi
  fi

  if [[ -f "${GPU_WORKFLOW_FILE}" ]]; then
    if curl -sf -X POST "${API_URL}/workflows?lookup_by_name=true" \
      -H "x-api-key: ${KEEP_API_KEY}" \
      -F "file=@${GPU_WORKFLOW_FILE}" \
      -o /tmp/keep-demo-gpu-workflow.json; then
      echo "Uploaded Keep workflow: ${GPU_WORKFLOW_FILE}"
    else
      echo "GPU workflow upload skipped (check API key / existing workflow)."
    fi
  else
    echo "GPU workflow file missing: ${GPU_WORKFLOW_FILE}"
  fi
}

echo "Starting Keep API on :8080..."
make backend &
BACKEND_PID=$!

wait_for_api
setup_nvidia_gpu_demo
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
echo "  temporal-worker:   keep-ops (ListAndZipDirectory, RemediateNvidiaGpu)"
echo "  synthetic-checks:  keep-synth (HTTP/TCP/DNS probes)"
echo "  Provider mock:     http://localhost:8099 (Grafana/Mimir/VM + NVIDIA GPU)"
echo "  NetBox:            http://localhost:8000 (admin/admin; seed from mock Topology tab)"
echo "  Catalog UI:        /catalog/synthetic-checks  and  /catalog/temporal-workflows"
echo ""
echo "NVIDIA GPU remediation demo is ready with make start:"
echo "  1) open http://localhost:8099  → Grafana → GPU: rule + temp/mem"
echo "  2) Keep Incidents → NVIDIA_GPU_* (auto Temporal remediate → resolve)"
echo "  3) Force fail path: NVIDIA GPU server tab → Force fail → re-fire"
echo "  Re-run setup only: make demo-nvidia-gpu"
echo ""
echo "AI DC synthetic checks (NVIDIA + AMD inference/training) are seeded when"
echo "  a Temporal provider is connected. UI: Catalog → Synthetic checks"
echo "  Fail a probe: http://localhost:8099 → Synthetic checks tab"
echo "  Re-seed: make register-ai-dc-synthetic-checks"
echo ""
echo "Press Ctrl+C to stop backend/frontend."
echo "Use 'make stop' to also stop Docker deps (incl. provider-mock)."
echo ""

wait -n "${BACKEND_PID}" "${FRONTEND_PID}" || true
wait || true
