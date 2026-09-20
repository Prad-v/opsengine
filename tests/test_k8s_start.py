"""k8s-start builds local backend images only; prod uses published Helm images."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = ROOT / "Makefile"
DEPLOY = ROOT / "scripts" / "deploy_kind.sh"
K8S_UI = ROOT / "scripts/k8s_ui.sh"
KIND_VALUES = ROOT / "helm" / "keep-values-kind.yaml"
PROD_VALUES = ROOT / "helm" / "keep-values-prod.yaml"
KIND_CLUSTER = ROOT / "helm" / "kind-opsengine.yaml"


def test_makefile_has_k8s_start_prod_and_ui():
    text = MAKEFILE.read_text()
    assert "k8s-start:" in text
    assert "k8s-start-fresh:" in text
    assert "k8s-prod:" in text
    assert "k8s-ui:" in text
    assert "K8S_FRESH=1" in text
    assert "K8S_UI=1" in text
    assert "MODE=dev" in text
    assert "MODE=prod" in text


def test_deploy_kind_skips_frontend_image_in_dev():
    text = DEPLOY.read_text()
    assert "docker-compose.alpine-wheels.yml" in text
    assert "docker-compose.local.yml" in text
    assert "keep-backend" in text
    assert "compose_build docker-compose.local.yml keep-backend" in text
    assert "compose_build docker-compose.local.yml keep-backend keep-frontend" not in text
    assert "kind load docker-image keep-frontend:local" not in text
    assert "docker-compose.temporal.yml" in text
    assert "provider-mock" in text
    assert "build --no-cache" in text
    assert "K8S_FRESH" in text
    assert 'DEV_NAMESPACE="${DEV_NAMESPACE:-keep}"' in text
    assert 'PROD_NAMESPACE="${PROD_NAMESPACE:-keep-prod}"' in text
    assert "deploy_dev" in text
    assert "deploy_prod" in text
    assert 'K8S_UI="${K8S_UI:-1}"' in text
    assert "scripts/k8s_ui.sh" in text


def test_local_values_disable_incluster_ui():
    text = KIND_VALUES.read_text()
    assert "frontend:" in text
    assert "enabled: false" in text
    assert "repository: keep-backend" in text
    assert "tag: local" in text
    assert "keep-frontend" not in text
    assert "ingress:" in text
    assert "enabled: false" in text
    assert "AUTH_TYPE" in text
    assert "DB" in text
    assert "KEEP_JWT_SECRET" in text
    assert "KEEP_DEFAULT_USERNAME" in text
    assert "KEEP_FORCE_RESET_DEFAULT_PASSWORD" in text
    assert "KEEP_EVENT_WORKERS" in text
    assert "DATABASE_POOL_SIZE" in text
    assert "resources:" in text
    assert "--workers" in text
    assert '"2"' in text


def test_prod_values_use_published_images_and_incluster_ui():
    text = PROD_VALUES.read_text()
    assert "enabled: true" in text
    assert "keep-backend:local" not in text
    assert "keep-frontend:local" not in text
    assert "tag: local" not in text
    uses_official = "us-central1-docker.pkg.dev/keephq/keep/keep-api" in text
    uses_ci_artifact = "repository: keep-backend" in text
    assert uses_official or uses_ci_artifact


def test_kind_maps_api_and_websocket_host_ports():
    text = KIND_CLUSTER.read_text()
    assert "containerPort: 30080" in text
    assert "hostPort: 8080" in text
    assert "containerPort: 30601" in text
    assert "hostPort: 6001" in text


def test_k8s_ui_points_at_kind_api():
    text = K8S_UI.read_text()
    assert "http://localhost:8080" in text
    assert "http://localhost:3000" in text
    assert "http://localhost:8099" in text
    assert "http://localhost:8233" in text
    assert "npm run dev" in text
    assert "DEV_NAMESPACE" in text
    assert "port-forward" in text
    assert "keep-backend" in text
    assert "API_URL=http://localhost:8080" in text
    assert "AUTH_TYPE=DB" in text
    assert "AUTH_SECRET=k8s-dev-nextauth-secret" in text
    assert "AUTH_DEBUG=false" in text
