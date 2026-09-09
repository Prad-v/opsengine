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

echo "Starting Keep API on :8080..."
make backend &
BACKEND_PID=$!

wait_for_api

echo "Starting Keep UI on :3000..."
make frontend &
FRONTEND_PID=$!

echo ""
echo "All services started:"
echo "  UI:       http://localhost:3000"
echo "  API:      http://localhost:8080"
echo "  Postgres: localhost:5432"
echo "  Redis:    localhost:6379"
echo "  Soketi:   localhost:6001"
echo ""
echo "Press Ctrl+C to stop backend/frontend."
echo "Use 'make stop' to also stop Docker deps."
echo ""

wait -n "${BACKEND_PID}" "${FRONTEND_PID}" || true
wait || true
