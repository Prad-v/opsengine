"""NVIDIA GPU datacenter topology YAML import (region/row/rack/GPU)."""

from __future__ import annotations

from pathlib import Path

from sqlmodel import select

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.db.topology import TopologyApplication, TopologyService
from keep.functions import cyaml
from keep.topologies.topologies_service import TopologiesService

ROOT = Path(__file__).resolve().parents[1]
TOPOLOGY_YAML = ROOT / "examples" / "topologies" / "nvidia-gpu-datacenter.yml"


def test_nvidia_gpu_topology_yaml_exists():
    assert TOPOLOGY_YAML.is_file()
    data = cyaml.safe_load(TOPOLOGY_YAML.read_text())
    names = {svc["service"] for svc in data["services"]}
    assert {
        "us-west-2",
        "ai-dc-1",
        "row-a",
        "row-b",
        "rack-11",
        "rack-12",
        "rack-21",
        "gpu-node-a01",
        "gpu-node-a03",
        "gpu-node-b01",
        "gpu-node-a03-gpu0",
        "gpu-inference",
    }.issubset(names)
    assert data["applications"][0]["name"] == "NVIDIA GPU Inference"
    assert len(data["dependencies"]) >= 17


def test_nvidia_gpu_topology_import_to_db(db_session):
    data = cyaml.safe_load(TOPOLOGY_YAML.read_text())
    TopologiesService.import_to_db(data, db_session, SINGLE_TENANT_UUID)

    services = db_session.exec(
        select(TopologyService).where(TopologyService.tenant_id == SINGLE_TENANT_UUID)
    ).all()
    names = {svc.service for svc in services}
    assert "gpu-inference" in names
    assert "gpu-node-a03-gpu0" in names
    assert "rack-12" in names
    assert "row-a" in names
    assert "us-west-2" in names

    apps = db_session.exec(
        select(TopologyApplication).where(
            TopologyApplication.tenant_id == SINGLE_TENANT_UUID
        )
    ).all()
    assert any(app.name == "NVIDIA GPU Inference" for app in apps)

    inference = next(svc for svc in services if svc.service == "gpu-inference")
    gpu = next(svc for svc in services if svc.service == "gpu-node-a03-gpu0")
    assert any(dep.depends_on_service_id == gpu.id for dep in inference.dependencies)


def test_demo_scripts_seed_nvidia_topology():
    demo = (ROOT / "scripts" / "demo_mock_nvidia_gpu.sh").read_text()
    hybrid = (ROOT / "scripts" / "run-hybrid-local.sh").read_text()
    e2e = (ROOT / "scripts" / "e2e_k8s_nvidia_gpu.sh").read_text()
    makefile = (ROOT / "Makefile").read_text()
    assert "register_nvidia_gpu_topology.py" in demo
    assert "register_nvidia_gpu_topology.py" in hybrid
    assert "register_nvidia_gpu_topology.py" in e2e
    assert "register-nvidia-gpu-topology" in makefile
    docs = (ROOT / "docs" / "overview" / "nvidia-gpu-topology.mdx").read_text()
    mint = (ROOT / "docs" / "mint.json").read_text()
    assert "overview/nvidia-gpu-topology" in mint
    assert "region" in docs and "rack" in docs and "gpu_id" in docs
    workflow = (ROOT / "examples" / "workflows" / "mock-nvidia-gpu-remediate.yml").read_text()
    assert "alert.labels.host" in workflow
    assert "alert.labels.gpu" in workflow
    assert "alert.labels.rack" in workflow
    assert 'labels.code.startsWith("NVIDIA_GPU")' in workflow


def test_nvidia_gpu_docs_cover_netbox_configure():
    docs = (ROOT / "docs" / "overview" / "nvidia-gpu-topology.mdx").read_text()
    assert "Configure Keep with NetBox" in docs
    assert "/api/netbox/configure-keep" in docs

