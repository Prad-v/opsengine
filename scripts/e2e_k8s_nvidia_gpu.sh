#!/usr/bin/env bash
# Exercise NVIDIA GPU remediations against a kind deploy (make k8s-start).
# Does not start Docker Compose workers — uses in-cluster Keep / mock / Temporal.
set -euo pipefail

KEEP_API="${KEEP_API:-http://localhost:8080}"
KEEP_API_KEY="${KEEP_API_KEY:-keepappkey}"
MOCK_URL="${MOCK_URL:-http://localhost:8099}"
# URLs the mock *pod* uses to reach Keep and itself.
INCLUSTER_KEEP="${INCLUSTER_KEEP:-http://keep-backend:8080}"
INCLUSTER_MOCK="${INCLUSTER_MOCK:-http://provider-mock:8099}"
WORKFLOW_FILE="${WORKFLOW_FILE:-examples/workflows/mock-nvidia-gpu-remediate.yml}"
TIMEOUT_SECS="${TIMEOUT_SECS:-180}"

auth=(-H "x-api-key: ${KEEP_API_KEY}" -H "Accept: application/json")

wait_http() {
  local url="$1" name="$2" n=0
  echo "==> Waiting for ${name} (${url})"
  until curl -sf "$url" >/dev/null; do
    n=$((n + 1))
    if [[ "$n" -ge 60 ]]; then
      echo "timeout waiting for ${name}" >&2
      exit 1
    fi
    sleep 2
  done
}

keep_get() {
  curl -sf --globoff "${auth[@]}" "$@"
}

echo "==> Health checks"
wait_http "${KEEP_API}/healthcheck" "Keep API"
wait_http "${MOCK_URL}/api/health" "provider-mock"

echo "==> Register Grafana + Temporal (in-cluster Keep URL)"
for provider in grafana temporal; do
  code=$(curl -sS -o /tmp/k8s-reg-${provider}.json -w "%{http_code}" \
    -X POST "${MOCK_URL}/api/register" \
    -H "Content-Type: application/json" \
    -d "{
      \"provider\": \"${provider}\",
      \"keep_api_url\": \"${INCLUSTER_KEEP}\",
      \"keep_api_key\": \"${KEEP_API_KEY}\",
      \"public_base_url\": \"${INCLUSTER_MOCK}\"
    }")
  echo "    ${provider} HTTP ${code}: $(head -c 200 /tmp/k8s-reg-${provider}.json)"
done

echo "==> Providers installed"
keep_get "${KEEP_API}/providers" | python3 -c '
import json, sys
data = json.load(sys.stdin)
rows = data.get("installed_providers") or data.get("providers") or []
for p in rows:
    if not isinstance(p, dict):
        continue
    name = (p.get("details") or {}).get("name") or p.get("name")
    print(f"    {p.get('type')} id={p.get('id')} name={name}")
'

echo "==> Register RemediateNvidiaGpu catalog"
KEEP_API_URL="${KEEP_API}" KEEP_API_KEY="${KEEP_API_KEY}" \
  python3 scripts/register_temporal_nvidia_gpu_catalog.py

echo "==> Seed NVIDIA GPU Service Topology"
KEEP_API_URL="${KEEP_API}" KEEP_API_KEY="${KEEP_API_KEY}" \
  python3 scripts/register_nvidia_gpu_topology.py || true

echo "==> Upload GPU remediate workflow"
wf_code=$(curl -sS -o /tmp/k8s-wf.json -w "%{http_code}" \
  -X POST "${KEEP_API}/workflows?lookup_by_name=true" \
  "${auth[@]}" \
  -F "file=@${WORKFLOW_FILE}")
echo "    workflow HTTP ${wf_code}: $(head -c 240 /tmp/k8s-wf.json)"

echo "==> Reset mock GPU server"
curl -sf -X POST "${MOCK_URL}/api/gpu/server/reset" -H "Content-Type: application/json" -d '{}' >/dev/null
curl -sf -X POST "${MOCK_URL}/api/gpu/server/mode" -H "Content-Type: application/json" -d '{"force_fail": false}' >/dev/null

echo "==> Fire GPU: rule + temp/mem (success path)"
curl -sf -X POST "${MOCK_URL}/api/grafana/create-gpu-incident-demo" \
  -H "Content-Type: application/json" \
  -d "{
    \"keep_api_url\": \"${INCLUSTER_KEEP}\",
    \"keep_api_key\": \"${KEEP_API_KEY}\",
    \"create_rule\": true,
    \"send_all_gpu\": false
  }" | python3 -m json.tool | head -40

echo "==> Poll for resolved GPU incident"
deadline=$((SECONDS + TIMEOUT_SECS))
resolved=""
while (( SECONDS < deadline )); do
  keep_get "${KEEP_API}/incidents?limit=50" > /tmp/k8s-incidents.json || true
  resolved=$(python3 - <<'PY'
import json
data=json.load(open("/tmp/k8s-incidents.json"))
items = data.get("items") or data.get("incidents") or (data if isinstance(data, list) else [])
for inc in items:
    name=(inc.get("user_generated_name") or inc.get("name") or "")
    if "GPU" not in name and "gpu" not in name.lower():
        continue
    status=inc.get("status")
    print(f"{inc.get('id')}|{status}|{name}")
    if status == "resolved":
        break
PY
)
  echo "    ${resolved//$'\n'/; }"
  if [[ "$resolved" == *"|resolved|"* ]]; then
    break
  fi
  sleep 5
done

if [[ "$resolved" != *"|resolved|"* ]]; then
  echo "FAIL: no resolved GPU incident within ${TIMEOUT_SECS}s" >&2
  echo "incidents:" >&2
  cat /tmp/k8s-incidents.json >&2
  echo "worker logs:" >&2
  kubectl -n keep logs deploy/temporal-worker --tail=40 >&2 || true
  echo "backend logs:" >&2
  kubectl -n keep logs deploy/keep-backend --tail=40 >&2 || true
  exit 1
fi

echo "==> Mock remediations (expect ok)"
incident_id="${resolved%%|*}"
catalog_id=$(keep_get "${KEEP_API}/temporal-workflows" | python3 -c '
import json,sys
rows=json.load(sys.stdin)
print(next(e["id"] for e in rows if e.get("catalog_key")=="remediate-nvidia-gpu"))
')
ensure_ok_remediation() {
  curl -sf "${MOCK_URL}/api/gpu/server" | python3 -c '
import json,sys
data=json.load(sys.stdin)
oks=[r for r in (data.get("remediations") or []) if r.get("ok") is True]
print(len(oks))
'
}
if [[ "$(ensure_ok_remediation)" == "0" ]]; then
  echo "    no remediations yet — starting catalog workflow for ${incident_id}"
  curl -sf --globoff -X POST "${KEEP_API}/temporal-workflows/${catalog_id}/start" \
    "${auth[@]}" -H "Content-Type: application/json" \
    -d "{\"incident_id\": \"${incident_id}\"}" >/dev/null
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    [[ "$(ensure_ok_remediation)" != "0" ]] && break
    sleep 2
  done
fi
curl -sf "${MOCK_URL}/api/gpu/server" | python3 -c '
import json,sys
data=json.load(sys.stdin)
rems=data.get("remediations") or []
oks=[r for r in rems if r.get("ok") is True]
print("remediations:", len(rems), "ok:", len(oks))
if not oks:
    raise SystemExit("no successful GPU remediations on mock server")
print(oks[-1])
'

echo "==> Failure path (force fail + catalog start)"
curl -sf -X POST "${MOCK_URL}/api/gpu/server/mode" -H "Content-Type: application/json" -d '{"force_fail": true}' >/dev/null
curl -sf -X DELETE "${MOCK_URL}/api/gpu/emails" >/dev/null
incident_id="${resolved%%|*}"
catalog_id=$(keep_get "${KEEP_API}/temporal-workflows" | python3 -c '
import json,sys
rows=json.load(sys.stdin)
print(next(e["id"] for e in rows if e.get("catalog_key")=="remediate-nvidia-gpu"))
')
start_code=$(curl -sS --globoff -o /tmp/k8s-start-wf.json -w "%{http_code}" \
  -X POST "${KEEP_API}/temporal-workflows/${catalog_id}/start" \
  "${auth[@]}" -H "Content-Type: application/json" \
  -d "{\"incident_id\": \"${incident_id}\"}")
echo "    catalog start HTTP ${start_code} incident=${incident_id}: $(head -c 180 /tmp/k8s-start-wf.json)"

fail_deadline=$((SECONDS + TIMEOUT_SECS))
got_email=""
while (( SECONDS < fail_deadline )); do
  emails=$(curl -sf "${MOCK_URL}/api/gpu/emails")
  count=$(python3 -c 'import json,sys; print(len(json.load(sys.stdin).get("emails") or []))' <<<"$emails")
  echo "    failure emails: ${count}"
  if [[ "$count" -ge 1 ]]; then
    got_email=1
    echo "$emails" | python3 -m json.tool | head -30
    break
  fi
  sleep 5
done

if [[ -z "$got_email" ]]; then
  echo "FAIL: no failure email after Force fail" >&2
  kubectl -n keep logs deploy/temporal-worker --tail=40 >&2 || true
  exit 1
fi

echo ""
echo "E2E OK: success path resolved a GPU incident; failure path posted a mock ops email."
