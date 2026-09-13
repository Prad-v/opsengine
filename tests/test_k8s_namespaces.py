"""Two kind namespaces: keep (local images) and keep-prod (published Helm)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "scripts" / "deploy_kind.sh"
BUMP = ROOT / "scripts" / "bump_helm_charts.sh"
PUBLISH = ROOT / ".github" / "workflows" / "publish-k8s-images.yml"
WORKER_PROD = ROOT / "helm" / "temporal-worker" / "values-prod.yaml"
MOCK_PROD = ROOT / "helm" / "provider-mock" / "values-prod.yaml"


def test_deploy_creates_both_namespaces():
    text = DEPLOY.read_text()
    assert "keep-prod" in text
    assert "ensure_namespaces" in text
    assert "keephq/keep" in text
    assert "keep-values-kind.yaml" in text
    assert "keep-values-prod.yaml" in text


def test_prod_overlays_use_keep_prod_dns():
    worker = WORKER_PROD.read_text()
    mock = MOCK_PROD.read_text()
    assert "keep-backend.keep-prod.svc.cluster.local" in worker
    assert "provider-mock.keep-prod.svc.cluster.local" in worker
    assert "keep-backend.keep-prod.svc.cluster.local" in mock
    assert "ghcr.io" in worker
    assert "ghcr.io" in mock


def test_ci_publishes_images_and_bumps_helm():
    workflow = PUBLISH.read_text()
    bump = BUMP.read_text()
    assert "ghcr.io" in workflow
    assert "keep-backend" in workflow
    assert "keep-frontend" in workflow
    assert "keep-temporal-worker" in workflow
    assert "keep-provider-mock" in workflow
    assert "bump_helm_charts.sh" in workflow
    assert "[skip ci]" in workflow
    assert "IMAGE_REGISTRY" in bump
    assert "keep-values-prod.yaml" in bump
