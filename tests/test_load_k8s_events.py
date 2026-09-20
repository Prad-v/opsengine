"""Unit tests for the kind/API event load harness (no cluster required)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "load_k8s_events.py"


def _load_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("load_k8s_events", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def load_mod():
    return _load_module()


def test_script_is_valid_python():
    ast.parse(SCRIPT.read_text())


def test_build_alert_unique_fingerprints(load_mod):
    a = load_mod.build_alert(0, run_id="r1")
    b = load_mod.build_alert(1, run_id="r1")
    assert a["fingerprint"] != b["fingerprint"]
    assert a["fingerprint"].startswith("scale-r1-")
    assert a["source"] == ["keep"]
    assert a["labels"]["suite"] == "load_k8s_events"


def test_chunked_batches(load_mod):
    items = list(range(50))
    batches = load_mod.chunked(items, 20)
    assert len(batches) == 3
    assert [len(b) for b in batches] == [20, 20, 10]


def test_chunked_rejects_empty_batch(load_mod):
    with pytest.raises(ValueError):
        load_mod.chunked([1], 0)


def test_parse_args_defaults(load_mod, monkeypatch):
    monkeypatch.delenv("COUNT", raising=False)
    args = load_mod.parse_args([])
    assert args.count == 2000
    assert args.concurrency == 20
    assert args.batch_size == 20
    assert args.api.endswith(":8080") or "8080" in args.api


def test_makefile_and_docs_wire_load_target():
    makefile = (ROOT / "Makefile").read_text()
    assert "k8s-load:" in makefile
    assert "scripts/load_k8s_events.py" in makefile
    values = (ROOT / "helm" / "keep-values-kind.yaml").read_text()
    assert "KEEP_EVENT_WORKERS" in values
    assert "DATABASE_POOL_SIZE" in values
    assert "resources:" in values
    assert '--workers' in values
    docs = (ROOT / "docs" / "deployment" / "scale-1m-events-architecture.mdx").read_text()
    assert "load_k8s_events" in docs or "k8s-load" in docs
