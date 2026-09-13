"""CI must package Helm charts and upload Docker/Helm artifacts."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLISH = ROOT / ".github" / "workflows" / "publish-k8s-images.yml"
PACKAGE = ROOT / "scripts" / "package_ci_artifacts.sh"
BUMP = ROOT / "scripts" / "bump_helm_charts.sh"
E2E = ROOT / ".github" / "workflows" / "test-pr-e2e.yml"
RUN_E2E = ROOT / ".github" / "workflows" / "run-e2e-tests.yml"


def test_publish_workflow_uploads_github_artifacts():
    text = PUBLISH.read_text()
    assert "actions/upload-artifact@v4" in text
    assert "opsengine-docker-images-" in text
    assert "opsengine-helm-charts-" in text
    assert "package_ci_artifacts.sh" in text
    assert "SAVE_IMAGES=" in text
    assert "NPM_CI=0" in text
    assert "IGNORE_TS_ERRORS=1" in text
    assert "build-frontend" in text
    assert "build-backend" in text
    assert "ALPINE_WHEELS_IMAGE=keep-api-alpine-wheels:py313" in text
    assert "docker build -f docker/Dockerfile.api" in text
    assert "docker build -f docker/Dockerfile.ui" in text


def test_package_script_covers_charts_and_images():
    text = PACKAGE.read_text()
    assert 'package "$chart"' in text
    assert "helm/temporal" in text
    assert "helm/temporal-worker" in text
    assert "helm/provider-mock" in text
    assert "helm/synthetic-checks" in text
    assert "docker save" in text
    assert "keep-backend" in text
    assert "keep-frontend" in text
    assert "keep-temporal-worker" in text
    assert "keep-provider-mock" in text


def test_bump_script_allows_local_artifact_names():
    text = BUMP.read_text()
    assert 'IMAGE_REGISTRY="${IMAGE_REGISTRY:-}"' in text
    assert "image_repo" in text
    assert "keep-backend" in text
    assert "keep-frontend" in text


def test_e2e_passes_images_via_artifacts():
    e2e = E2E.read_text()
    run = RUN_E2E.read_text()
    assert "actions/upload-artifact@v4" in e2e
    assert "e2e-keep-frontend" in e2e
    assert "e2e-keep-backend" in e2e
    assert "actions/download-artifact@v4" in run
    assert "docker load" in run
