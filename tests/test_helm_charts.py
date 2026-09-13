"""Render local Helm charts in Docker (alpine/helm)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELM_IMAGE = "alpine/helm:3.16.4"

CHARTS = (
    (
        "temporal",
        "helm/temporal",
        ["helm/temporal/values.yaml", "helm/temporal/values-dev.yaml"],
        ("kind: Deployment", "kind: Service", "start-dev"),
    ),
    (
        "temporal-worker",
        "helm/temporal-worker",
        ["helm/temporal-worker/values.yaml", "helm/temporal-worker/values-dev.yaml"],
        ("kind: Deployment", "GPU_MOCK_URL", "KEEP_API_URL"),
    ),
    (
        "provider-mock",
        "helm/provider-mock",
        ["helm/provider-mock/values.yaml", "helm/provider-mock/values-dev.yaml"],
        ("kind: Deployment", "kind: Service", "KEEP_API_URL", "/api/health"),
    ),
    (
        "synthetic-checks",
        "helm/synthetic-checks",
        ["helm/synthetic-checks/values.yaml", "helm/synthetic-checks/values-dev.yaml"],
        ("kind: Deployment", "TEMPORAL_ADDRESS"),
    ),
    (
        "temporal-worker-prod",
        "helm/temporal-worker",
        ["helm/temporal-worker/values.yaml", "helm/temporal-worker/values-prod.yaml"],
        ("kind: Deployment", "keep-prod", "GPU_MOCK_URL"),
    ),
    (
        "provider-mock-prod",
        "helm/provider-mock",
        ["helm/provider-mock/values.yaml", "helm/provider-mock/values-prod.yaml"],
        ("kind: Deployment", "keep-prod", "KEEP_API_URL"),
    ),
)


@pytest.mark.integration
@pytest.mark.parametrize("release,chart,value_files,must_contain", CHARTS)
def test_helm_template_renders(release, chart, value_files, must_contain):
    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{ROOT}:/work:ro",
        "-w",
        "/work",
        HELM_IMAGE,
        "template",
        release,
        chart,
    ]
    for value_file in value_files:
        cmd.extend(["-f", value_file])
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr or result.stdout
    for snippet in must_contain:
        assert snippet in result.stdout, f"missing {snippet!r} in helm template output"
