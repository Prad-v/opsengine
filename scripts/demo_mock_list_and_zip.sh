#!/usr/bin/env bash
# Install and document the mock Grafana → Temporal ListAndZip e2e demo.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

API_URL="${KEEP_API_URL:-http://localhost:8080}"
API_KEY="${KEEP_API_KEY:-keepappkey}"
WORKFLOW_FILE="${WORKFLOW_FILE:-examples/workflows/mock-grafana-list-and-zip.yml}"

echo "==> Checking Keep API at ${API_URL}"
if ! curl -sf -H "x-api-key: ${API_KEY}" "${API_URL}/providers" >/dev/null; then
  echo "Keep API is not reachable. Run: make start" >&2
  exit 1
fi

echo "==> Ensuring Temporal worker is up (ListAndZipDirectory / keep-ops)"
docker compose -f docker-compose.temporal.yml up -d --build temporal-worker >/dev/null

echo "==> Registering ListAndZipDirectory in Temporal catalog"
KEEP_API_URL="${API_URL}" KEEP_API_KEY="${API_KEY}" \
  "${ROOT}/.venv/bin/python" scripts/register_temporal_list_and_zip_catalog.py

echo "==> Applying Keep workflow ${WORKFLOW_FILE}"
if [[ -x "${ROOT}/.venv/bin/keep" ]]; then
  KEEP_API_URL="${API_URL}" KEEP_API_KEY="${API_KEY}" \
    "${ROOT}/.venv/bin/keep" workflow apply -f "${WORKFLOW_FILE}" || true
fi

# Prefer API upload (works even if CLI auth differs)
curl -sf -X POST "${API_URL}/workflows?lookup_by_name=true" \
  -H "x-api-key: ${API_KEY}" \
  -F "file=@${WORKFLOW_FILE}" \
  -o /tmp/keep-demo-workflow.json \
  && echo "Workflow uploaded:" && cat /tmp/keep-demo-workflow.json && echo \
  || echo "Workflow upload returned non-200 — check API logs / existing workflow id"

for extra in \
  examples/workflows/mock-mimir-disk.yml \
  examples/workflows/mock-victoriametrics-memory.yml \
  examples/workflows/alert-code-console.yml
do
  echo "==> Applying ${extra}"
  curl -sf -X POST "${API_URL}/workflows?lookup_by_name=true" \
    -H "x-api-key: ${API_KEY}" \
    -F "file=@${extra}" \
    -o /dev/null \
    && echo "    uploaded ${extra}" \
    || echo "    ${extra} upload skipped"
done

echo "==> Registering reserved payments alert codes (HIGH_CPU / HIGH_MEMORY / DISK_SPACE_LOW)"
KEEP_API_URL="${API_URL}" KEEP_API_KEY="${API_KEY}" \
  "${ROOT}/.venv/bin/python" scripts/register_alert_codes_payments.py || true

cat <<EOF

============================================================
Demo ready: Mock Grafana → Incident → Temporal ListAndZip
============================================================

1) Open mock UI (started with make start / make deps):
     open http://localhost:8099
     # Restart only the mock if needed: make mock-providers

2) Register providers in mock UI:
     - Alert sources → Grafana → Register
     - Temporal tab → Register Temporal

3) Fire the correlation demo:
     Grafana tab → "Payments: rule + send both"
     (2 alerts, shared service=payments-api → 1 incident)
     # Or NVIDIA GPU pack: "GPU: rule + temp/mem" / "GPU: rule + all alerts"

4) In Keep UI (http://localhost:3000):
     - Incidents → open Payments HIGH_CPU / HIGH_MEMORY / INC-*
     - Timeline: correlated Grafana alerts
     - Workflows: Keep execution + Temporal start
     - Overview enrichments: remediation, list_path, temporal_demo

5) Verify Temporal worker output:
     open http://localhost:8233
     docker exec keep-temporal-worker ls -la /data/output
     docker logs keep-temporal-worker --tail 50

Optional: builder path — Add step → Temporal catalog → List and Zip Directory
============================================================
EOF
