#!/usr/bin/env bash
# Install / re-install the mock NVIDIA GPU → Temporal remediation e2e demo.
# Note: make start already runs this setup automatically (AUTO_SETUP_NVIDIA_GPU_DEMO=1).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

API_URL="${KEEP_API_URL:-http://localhost:8080}"
API_KEY="${KEEP_API_KEY:-keepappkey}"
WORKFLOW_FILE="${WORKFLOW_FILE:-examples/workflows/mock-nvidia-gpu-remediate.yml}"
MOCK_URL="${MOCK_URL:-http://127.0.0.1:8099}"
PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-http://localhost:8099}"

echo "==> Checking Keep API at ${API_URL}"
if ! curl -sf -H "x-api-key: ${API_KEY}" "${API_URL}/providers" >/dev/null; then
  echo "Keep API is not reachable. Run: make start" >&2
  exit 1
fi

echo "==> Ensuring Temporal worker is up (RemediateNvidiaGpu / keep-ops)"
docker compose -f docker-compose.temporal.yml up -d --build temporal-worker >/dev/null

echo "==> Ensuring provider-mock is up (NVIDIA GPU server :8099)"
docker compose -f backend/services/provider-mock/docker-compose.yml up --build -d >/dev/null

echo "==> Registering mock Temporal + Grafana providers (best-effort)"
for provider in temporal grafana; do
  curl -sf -X POST "${MOCK_URL}/api/register" \
    -H "Content-Type: application/json" \
    -d "{
      \"provider\": \"${provider}\",
      \"keep_api_url\": \"${API_URL}\",
      \"keep_api_key\": \"${API_KEY}\",
      \"public_base_url\": \"${PUBLIC_BASE_URL}\"
    }" >/dev/null \
    && echo "    registered ${provider}" \
    || echo "    ${provider} register skipped (may already exist)"
done

echo "==> Registering RemediateNvidiaGpu in Temporal catalog"
KEEP_API_URL="${API_URL}" KEEP_API_KEY="${API_KEY}" \
  "${ROOT}/.venv/bin/python" scripts/register_temporal_nvidia_gpu_catalog.py

echo "==> Applying Keep workflow ${WORKFLOW_FILE}"
if [[ -x "${ROOT}/.venv/bin/keep" ]]; then
  KEEP_API_URL="${API_URL}" KEEP_API_KEY="${API_KEY}" \
    "${ROOT}/.venv/bin/keep" workflow apply -f "${WORKFLOW_FILE}" || true
fi

curl -sf -X POST "${API_URL}/workflows?lookup_by_name=true" \
  -H "x-api-key: ${API_KEY}" \
  -F "file=@${WORKFLOW_FILE}" \
  -o /tmp/keep-demo-gpu-workflow.json \
  && echo "Workflow uploaded:" && cat /tmp/keep-demo-gpu-workflow.json && echo \
  || echo "Workflow upload returned non-200 — check API logs / existing workflow id"

echo "==> Registering reserved NVIDIA GPU alert codes"
KEEP_API_URL="${API_URL}" KEEP_API_KEY="${API_KEY}" \
  "${ROOT}/.venv/bin/python" scripts/register_alert_codes_nvidia_gpu.py || true

echo "==> Seeding NVIDIA GPU Service Topology (region/datacenter/row/rack/GPU)"
KEEP_API_URL="${API_URL}" KEEP_API_KEY="${API_KEY}" \
  "${ROOT}/.venv/bin/python" scripts/register_nvidia_gpu_topology.py || true

echo "==> Seeding AI DC synthetic checks (NVIDIA + AMD inference/training)"
KEEP_API_URL="${API_URL}" KEEP_API_KEY="${API_KEY}" \
  SYNTH_TARGET_BASE_URL="${SYNTH_TARGET_BASE_URL:-http://host.docker.internal:8099}" \
  "${ROOT}/.venv/bin/python" scripts/register_ai_dc_synthetic_checks.py || true

cat <<EOF

============================================================
Demo ready: NVIDIA GPU alerts → Incident → Temporal remediate
============================================================

Already included in: make start

1) Open mock UI:
     open http://localhost:8099

2) Fire success path:
     Grafana → "GPU: rule + temp/mem"
     Keep Incidents → GPU-* / NVIDIA_GPU_*
     Temporal remediates mock GPU server → incident status becomes resolved
     Mock UI → NVIDIA GPU server tab → remediations show ok

3) Failure path:
     Mock UI → NVIDIA GPU server → enable Force fail
     Re-fire GPU alerts (or create a new GPU incident)
     Temporal fails remediations → Failure emails inbox fills
     Incident stays open

4) Verify Temporal:
     open http://localhost:8233
     docker logs keep-temporal-worker --tail 80

Optional: Catalog → Alert codes (NVIDIA_GPU_* and SYNTH_*) and
          Catalog → Temporal workflow → Remediate NVIDIA GPU
          Catalog → Synthetic checks (NVIDIA/AMD inference + training pack)
          Keep → Service Topology (region / datacenter / row / rack / GPU)
          Mock UI → Synthetic checks tab to fail a canary
============================================================
EOF
