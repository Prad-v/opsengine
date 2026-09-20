"""AI datacenter synthetic-check catalog (NVIDIA + AMD inference/training)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNTH_PROBES_PATH = (
    ROOT / "backend" / "services" / "provider-mock" / "app" / "synth_probes.py"
)


def _load_synth_probes():
    spec = importlib.util.spec_from_file_location(
        "provider_mock_synth_probes", SYNTH_PROBES_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ai_dc_synth_catalog_unique_and_labeled():
    synth = _load_synth_probes()
    checks = synth.build_keep_synthetic_checks(
        "http://host.docker.internal:8099", "mock-temporal"
    )
    keys = [item["check_key"] for item in checks]
    assert len(keys) == len(set(keys))
    assert len(checks) == len(synth.PROBE_SPECS)

    by_key = {item["check_key"]: item for item in checks}
    assert by_key["nvidia-inference-golden"]["prober"] == "http"
    assert by_key["nvidia-inference-golden"]["module_config"]["method"] == "POST"
    assert "SYNTH_OK" in by_key["nvidia-inference-golden"]["module_config"][
        "fail_if_body_not_matches_regexp"
    ]
    assert by_key["nvidia-inference-golden"]["labels"]["vendor"] == "nvidia"
    assert by_key["nvidia-inference-golden"]["labels"]["code"] == "SYNTH_NVIDIA_INFERENCE_GOLDEN"
    assert by_key["amd-inference-golden"]["labels"]["vendor"] == "amd"
    assert by_key["nvidia-nccl"]["labels"]["service"] == "gpu-training"
    assert by_key["training-submit"]["interval_seconds"] >= 60
    assert by_key["dc-control-plane"]["prober"] == "tcp"
    assert by_key["dc-control-plane"]["targets"] == ["host.docker.internal:8099"]

    codes = {item["code"] for item in synth.SYNTH_ALERT_CODES}
    assert codes == {spec["code"] for spec in synth.PROBE_SPECS}
    assert "SYNTH_NVIDIA_NCCL" in codes
    assert "SYNTH_AMD_RCCL" in codes


def test_ai_dc_synth_docs_and_make_wiring():
    makefile = (ROOT / "Makefile").read_text()
    hybrid = (ROOT / "scripts" / "run-hybrid-local.sh").read_text()
    demo = (ROOT / "scripts" / "demo_mock_nvidia_gpu.sh").read_text()
    mint = (ROOT / "docs" / "mint.json").read_text()
    docs = (ROOT / "docs" / "overview" / "ai-dc-synthetic-checks.mdx").read_text()
    synth_docs = (ROOT / "docs" / "overview" / "synthetic-checks.mdx").read_text()
    workflow = (ROOT / "examples" / "workflows" / "ai-dc-synthetic-firing.yml").read_text()

    assert "register-ai-dc-synthetic-checks" in makefile
    assert "register_ai_dc_synthetic_checks.py" in hybrid
    assert "register_ai_dc_synthetic_checks.py" in demo
    assert "overview/ai-dc-synthetic-checks" in mint
    assert "SYNTH_NVIDIA_INFERENCE_GOLDEN" in docs
    assert "max_duration_seconds" in synth_docs
    assert 'labels.code.startsWith("SYNTH_")' in workflow
