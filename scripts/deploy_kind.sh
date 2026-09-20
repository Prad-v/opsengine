#!/usr/bin/env bash
# Helm-install Keep + Temporal + temporal-worker + provider-mock on kind.
#
# MODE=dev  (make k8s-start)
#   Namespace keep — locally built backend / worker / mock images (no UI image).
#   Then starts the host UI (http://localhost:3000 → API http://localhost:8080).
#
# MODE=prod (make k8s-prod)
#   Namespace keep-prod — published Helm images (GHCR / official Keep chart).
#   In-cluster Keep UI via ingress (http://localhost).
#
# Incremental:  make k8s-start
# From scratch: make k8s-start-fresh  (K8S_FRESH=1 → compose build --no-cache)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLUSTER="${CLUSTER:-opsengine}"
MODE="${MODE:-dev}"
DEV_NAMESPACE="${DEV_NAMESPACE:-keep}"
PROD_NAMESPACE="${PROD_NAMESPACE:-keep-prod}"
WORKER_TAG="${WORKER_TAG:-0.1.1}"
MOCK_TAG="${MOCK_TAG:-0.1.0}"
K8S_FRESH="${K8S_FRESH:-0}"
K8S_UI="${K8S_UI:-1}"
BACKEND_NODEPORT="${BACKEND_NODEPORT:-30080}"
WEBSOCKET_NODEPORT="${WEBSOCKET_NODEPORT:-30601}"

COMPOSE="${COMPOSE:-docker compose}"
KIND="${KIND:-kind}"
HELM="${HELM:-helm}"
KUBECTL="${KUBECTL:-kubectl}"

cd "$ROOT"

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing required command: $1" >&2
    exit 1
  }
}

need docker
need kind
need helm
need kubectl

compose_build() {
  local file="$1"
  shift
  if [[ "${K8S_FRESH}" == "1" ]]; then
    $COMPOSE -f "$file" build --no-cache "$@"
  else
    $COMPOSE -f "$file" build "$@"
  fi
}

ensure_cluster() {
  if $KIND get clusters | grep -qx "$CLUSTER"; then
    echo "==> Reusing kind cluster ${CLUSTER}"
  else
    echo "==> Creating kind cluster ${CLUSTER}"
    $KIND create cluster --config helm/kind-opsengine.yaml
  fi
  $KUBECTL config use-context "kind-${CLUSTER}" >/dev/null
}

ensure_namespaces() {
  $KUBECTL create namespace "$DEV_NAMESPACE" --dry-run=client -o yaml | $KUBECTL apply -f - >/dev/null
  $KUBECTL create namespace "$PROD_NAMESPACE" --dry-run=client -o yaml | $KUBECTL apply -f - >/dev/null
}

install_ingress() {
  echo "==> Installing ingress-nginx (kind manifest)"
  $KUBECTL apply -f https://kind.sigs.k8s.io/examples/ingress/deploy-ingress-nginx.yaml
  $KUBECTL -n ingress-nginx rollout status deploy/ingress-nginx-controller --timeout=5m
  $KUBECTL -n ingress-nginx patch configmap ingress-nginx-controller --type merge \
    -p '{"data":{"allow-snippet-annotations":"true","annotations-risk-level":"Critical"}}' >/dev/null
}

helm_keep_repo() {
  $HELM repo add keephq https://keephq.github.io/helm-charts >/dev/null 2>&1 || true
  $HELM repo update keephq >/dev/null
}

# Official keep chart does not template service.nodePort; pin it after install.
pin_nodeport() {
  local ns="$1" svc="$2" port="$3" node_port="$4"
  $KUBECTL -n "$ns" patch svc "$svc" --type merge -p \
    "{\"spec\":{\"type\":\"NodePort\",\"ports\":[{\"name\":\"http\",\"port\":${port},\"targetPort\":\"http\",\"nodePort\":${node_port}}]}}" \
    >/dev/null 2>&1 || \
  $KUBECTL -n "$ns" patch svc "$svc" --type merge -p \
    "{\"spec\":{\"type\":\"NodePort\",\"ports\":[{\"port\":${port},\"targetPort\":${port},\"nodePort\":${node_port}}]}}" \
    >/dev/null
}

ensure_host_access() {
  local url="$1" ns="$2" svc="$3" local_port="$4" remote_port="$5"
  if curl -sf --max-time 3 "$url" >/dev/null 2>&1; then
    return 0
  fi
  echo "==> ${url} not reachable via kind NodePort; starting port-forward ${svc}"
  echo "    Recreate the cluster once so extraPortMappings apply: make k8s-stop && make k8s-start"
  nohup $KUBECTL -n "$ns" port-forward "svc/${svc}" "${local_port}:${remote_port}" \
    >/tmp/k8s-pf-${svc}.log 2>&1 &
  disown || true
  sleep 2
}

deploy_dev() {
  local ns="$DEV_NAMESPACE"

  if [[ "${K8S_FRESH}" == "1" ]]; then
    echo "==> Fresh mode: recompile Alpine grpcio and rebuild backend/worker/mock (--no-cache)"
  fi

  echo "==> Alpine musl wheels (grpcio / google-crc32c)"
  compose_build docker-compose.alpine-wheels.yml alpine-wheels

  echo "==> Keep API only (skip UI image — host npm run dev)"
  compose_build docker-compose.local.yml keep-backend

  echo "==> temporal-worker + provider-mock"
  COMPOSE_PROJECT_NAME=opsengine compose_build docker-compose.temporal.yml temporal-worker
  COMPOSE_PROJECT_NAME=opsengine compose_build backend/services/provider-mock/docker-compose.yml provider-mock

  docker tag "opsengine-temporal-worker:latest" "keep-temporal-worker:${WORKER_TAG}"
  docker tag "opsengine-provider-mock:latest" "keep-provider-mock:${MOCK_TAG}"

  ensure_cluster
  ensure_namespaces

  echo "==> Loading local images into kind (no frontend image)"
  $KIND load docker-image keep-backend:local --name "$CLUSTER"
  $KIND load docker-image "keep-temporal-worker:${WORKER_TAG}" --name "$CLUSTER"
  $KIND load docker-image "keep-provider-mock:${MOCK_TAG}" --name "$CLUSTER"

  install_ingress
  helm_keep_repo

  echo "==> Installing Keep into ${ns} (local images, frontend disabled)"
  $HELM upgrade --install keep keephq/keep \
    --namespace "$ns" --create-namespace \
    -f helm/keep-values-kind.yaml \
    --timeout 10m

  echo "==> Installing Temporal + worker + provider-mock into ${ns}"
  $HELM upgrade --install temporal "$ROOT/helm/temporal" \
    --namespace "$ns" \
    -f helm/temporal/values.yaml \
    -f helm/temporal/values-dev.yaml

  $HELM upgrade --install temporal-worker "$ROOT/helm/temporal-worker" \
    --namespace "$ns" \
    -f helm/temporal-worker/values.yaml \
    -f helm/temporal-worker/values-dev.yaml \
    --set "image.tag=${WORKER_TAG}"

  $HELM upgrade --install provider-mock "$ROOT/helm/provider-mock" \
    --namespace "$ns" \
    -f helm/provider-mock/values.yaml \
    -f helm/provider-mock/values-dev.yaml \
    --set "image.tag=${MOCK_TAG}"

  pin_nodeport "$ns" keep-backend 8080 "$BACKEND_NODEPORT"
  pin_nodeport "$ns" keep-websocket 6001 "$WEBSOCKET_NODEPORT"

  echo "==> Restarting workloads so kind-loaded :local images are picked up"
  $KUBECTL -n "$ns" rollout restart deploy/keep-backend deploy/temporal-worker deploy/provider-mock

  echo "==> Waiting for workloads"
  $KUBECTL -n "$ns" rollout status deploy/keep-backend --timeout=8m || true
  $KUBECTL -n "$ns" rollout status deploy/keep-websocket --timeout=3m || true
  $KUBECTL -n "$ns" rollout status deploy/temporal --timeout=3m || true
  $KUBECTL -n "$ns" rollout status deploy/temporal-worker --timeout=3m || true
  $KUBECTL -n "$ns" rollout status deploy/provider-mock --timeout=3m || true

  ensure_host_access "http://127.0.0.1:8080/healthcheck" "$ns" keep-backend 8080 8080
  ensure_host_access "http://127.0.0.1:6001" "$ns" keep-websocket 6001 6001

  echo ""
  echo "Kind cluster: ${CLUSTER}  (kubectl context kind-${CLUSTER})"
  echo "Namespaces:   ${DEV_NAMESPACE} (local images)   ${PROD_NAMESPACE} (make k8s-prod)"
  echo "Images: keep-backend:local  keep-temporal-worker:${WORKER_TAG}  keep-provider-mock:${MOCK_TAG}"
  echo "Keep UI:          http://localhost:3000"
  echo "Keep API:         http://localhost:8080"
  echo "API health:       http://localhost:8080/healthcheck"
  echo "API docs:         http://localhost:8080/docs"
  echo "Websocket:        http://localhost:6001"
  echo "Provider mock:    http://localhost:8099"
  echo "Temporal UI:      http://localhost:8233"
  echo ""
  $KUBECTL -n "$ns" get pods,svc
  echo ""
  $KUBECTL get ns "$DEV_NAMESPACE" "$PROD_NAMESPACE"

  if [[ "${K8S_UI}" == "1" ]]; then
    echo "==> Starting host UI (Ctrl+C stops the UI; the kind cluster stays up)"
    exec "$ROOT/scripts/k8s_ui.sh"
  fi
}

deploy_prod() {
  local ns="$PROD_NAMESPACE"

  ensure_cluster
  ensure_namespaces
  install_ingress
  helm_keep_repo

  echo "==> Installing Keep into ${ns} (published / GHCR images, in-cluster UI)"
  $HELM upgrade --install keep keephq/keep \
    --namespace "$ns" --create-namespace \
    -f helm/keep-values-prod.yaml \
    --timeout 15m

  echo "==> Installing Temporal + worker + provider-mock into ${ns}"
  $HELM upgrade --install temporal "$ROOT/helm/temporal" \
    --namespace "$ns" \
    -f helm/temporal/values.yaml \
    -f helm/temporal/values-prod.yaml

  $HELM upgrade --install temporal-worker "$ROOT/helm/temporal-worker" \
    --namespace "$ns" \
    -f helm/temporal-worker/values.yaml \
    -f helm/temporal-worker/values-prod.yaml

  $HELM upgrade --install provider-mock "$ROOT/helm/provider-mock" \
    --namespace "$ns" \
    -f helm/provider-mock/values.yaml \
    -f helm/provider-mock/values-prod.yaml

  echo "==> Waiting for workloads"
  $KUBECTL -n "$ns" rollout status deploy/keep-backend --timeout=8m || true
  $KUBECTL -n "$ns" rollout status deploy/keep-frontend --timeout=8m || true
  $KUBECTL -n "$ns" rollout status deploy/keep-websocket --timeout=3m || true
  $KUBECTL -n "$ns" rollout status deploy/temporal --timeout=3m || true
  $KUBECTL -n "$ns" rollout status deploy/temporal-worker --timeout=3m || true
  $KUBECTL -n "$ns" rollout status deploy/provider-mock --timeout=3m || true

  echo ""
  echo "Kind cluster: ${CLUSTER}  (kubectl context kind-${CLUSTER})"
  echo "Namespace:    ${ns}  (published Helm / GHCR images)"
  echo "Keep UI:      http://localhost"
  echo "Keep API:     http://localhost/v2"
  echo ""
  $KUBECTL -n "$ns" get pods,svc,ingress
}

case "$MODE" in
  dev) deploy_dev ;;
  prod) deploy_prod ;;
  *)
    echo "MODE must be dev or prod (got ${MODE})" >&2
    exit 1
    ;;
esac
