"""Unit tests for temporal-worker list-and-zip activities."""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

import pytest

# Import activities from the worker package path.
WORKER_ROOT = (
    Path(__file__).resolve().parents[1]
    / "backend"
    / "services"
    / "temporal-worker"
)


@pytest.fixture()
def worker_data(tmp_path, monkeypatch):
    root = tmp_path / "data"
    sample = root / "sample"
    sample.mkdir(parents=True)
    (sample / "readme.txt").write_text("hello")
    (sample / "a.txt").write_text("alpha")
    monkeypatch.setenv("TEMPORAL_WORKER_ROOT", str(root))
    monkeypatch.syspath_prepend(str(WORKER_ROOT))
    return root


def test_run_ls_and_create_zip(worker_data):
    from app.activities import create_zip_from_ls, run_ls

    ls_result = run_ls("sample")
    assert ls_result["exit_code"] == 0
    assert "readme.txt" in ls_result["stdout"]
    assert "a.txt" in ls_result["stdout"]

    zip_result = create_zip_from_ls(ls_result, incident_id="inc-1")
    zip_path = Path(zip_result["zip_path"])
    assert zip_path.exists()
    assert zip_result["bytes"] > 0
    assert zip_result["incident_id"] == "inc-1"

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        assert "ls-output.txt" in names
        content = zf.read("ls-output.txt").decode("utf-8")
        assert "readme.txt" in content


def test_run_ls_rejects_path_escape(worker_data):
    from app.activities import run_ls

    with pytest.raises(ValueError, match="outside worker root"):
        run_ls("../..")


def test_remediate_nvidia_gpu_success(worker_data, monkeypatch):
    from app import activities

    def fake_http(method, url, *, body=None, headers=None, timeout=30.0):
        assert method == "POST"
        assert url.endswith("/gpu/server/remediate")
        assert body["action"] == "reset_gpu"
        return 200, {"ok": True, "message": "done", "action": "reset_gpu"}

    monkeypatch.setattr(activities, "_http_json", fake_http)
    monkeypatch.setenv("GPU_MOCK_URL", "http://gpu-mock.test")
    result = activities.remediate_nvidia_gpu(
        {"incident_id": "inc-1", "action": "reset_gpu", "gpu_index": 0}
    )
    assert result["ok"] is True
    assert result["http_status"] == 200


def test_remediate_nvidia_gpu_failure_detail(worker_data, monkeypatch):
    from app import activities

    def fake_http(method, url, *, body=None, headers=None, timeout=30.0):
        return 503, {"detail": {"ok": False, "error": "forced fail"}}

    monkeypatch.setattr(activities, "_http_json", fake_http)
    result = activities.remediate_nvidia_gpu({"incident_id": "inc-2"})
    assert result["ok"] is False
    assert result["error"] == "forced fail"


def test_run_dcgm_diag_pass(worker_data, monkeypatch):
    from app import activities

    def fake_http(method, url, *, body=None, headers=None, timeout=30.0):
        assert method == "POST"
        assert url.endswith("/gpu/server/diag")
        assert body["suite"] == "2"
        return 200, {
            "ok": True,
            "result": "Pass",
            "recommendation": "RESET",
            "suite": "2",
            "tests": [{"name": "memory", "status": "Pass"}],
        }

    monkeypatch.setattr(activities, "_http_json", fake_http)
    monkeypatch.setenv("GPU_MOCK_URL", "http://gpu-mock.test")
    result = activities.run_dcgm_diag(
        {"incident_id": "inc-d1", "suite": "2", "gpu_index": 0}
    )
    assert result["ok"] is True
    assert result["diag_pass"] is True
    assert result["recommendation"] == "RESET"


def test_run_dcgm_diag_isolate(worker_data, monkeypatch):
    from app import activities

    def fake_http(method, url, *, body=None, headers=None, timeout=30.0):
        return 200, {
            "ok": True,
            "result": "Fail",
            "recommendation": "ISOLATE",
            "error_code": "DCGM_FR_FAULTY_MEMORY",
            "message": "memory failed",
        }

    monkeypatch.setattr(activities, "_http_json", fake_http)
    result = activities.run_dcgm_diag({"incident_id": "inc-d2"})
    assert result["ok"] is True
    assert result["diag_pass"] is False
    assert result["recommendation"] == "ISOLATE"
    assert result["error_code"] == "DCGM_FR_FAULTY_MEMORY"


def test_cordon_and_uncordon_nvidia_gpu(worker_data, monkeypatch):
    from app import activities

    calls: list[str] = []

    def fake_http(method, url, *, body=None, headers=None, timeout=30.0):
        calls.append(url)
        if url.endswith("/cordon"):
            assert body["drain"] is True
            return 200, {"ok": True, "cordoned": True, "drained": True, "host": body["host"]}
        if url.endswith("/uncordon"):
            return 200, {"ok": True, "cordoned": False, "drained": False, "host": body["host"]}
        raise AssertionError(url)

    monkeypatch.setattr(activities, "_http_json", fake_http)
    monkeypatch.setenv("GPU_MOCK_URL", "http://gpu-mock.test")
    c = activities.cordon_nvidia_gpu({"host": "gpu-node-a03", "incident_id": "inc-c"})
    assert c["ok"] is True
    assert c["cordoned"] is True
    u = activities.uncordon_nvidia_gpu({"host": "gpu-node-a03"})
    assert u["ok"] is True
    assert u["cordoned"] is False
    assert any(u.endswith("/cordon") for u in calls)
    assert any(u.endswith("/uncordon") for u in calls)


def test_dcgm_diag_suite_policy(worker_data):
    from app.dcgm_diag import requires_approval, requires_cordon, suite_level

    assert suite_level("1") == 1
    assert suite_level("2") == 2
    assert suite_level("long") == 3
    assert suite_level("xlong") == 4
    assert requires_cordon(1) is False
    assert requires_cordon(2) is True
    assert requires_approval(2) is False
    assert requires_approval(3) is True


def test_parse_dcgmi_json_fail(worker_data):
    from app.dcgm_diag import parse_dcgmi_json

    raw = {
        "test_categories": [
            {"category": "memory", "status": "Fail", "error_code": "DCGM_FR_FAULTY_MEMORY"},
            {"category": "pcie", "status": "Pass"},
        ]
    }
    parsed = parse_dcgmi_json(raw, suite="2", host="gpu-node-a03", gpu_index=0)
    assert parsed["result"] == "Fail"
    assert parsed["recommendation"] == "ISOLATE"
    assert parsed["error_code"] == "DCGM_FR_FAULTY_MEMORY"
    assert parsed["mode"] == "real"


def test_run_dcgm_diag_real_falls_back_to_mock(worker_data, monkeypatch):
    from app import activities
    from app import dcgm_diag

    def fake_cli(**kwargs):
        return {
            "ok": False,
            "error": "dcgmi binary not found on PATH",
            "mode": "real",
        }

    def fake_http(method, url, *, body=None, headers=None, timeout=30.0):
        assert url.endswith("/gpu/server/diag")
        return 200, {
            "ok": True,
            "result": "Pass",
            "recommendation": "RESET",
            "suite": "2",
        }

    monkeypatch.setattr(dcgm_diag, "run_dcgmi_cli", fake_cli)
    monkeypatch.setattr(activities, "_http_json", fake_http)
    monkeypatch.setenv("DCGM_DIAG_MODE", "real")
    monkeypatch.delenv("DCGM_DIAG_REQUIRE_REAL", raising=False)
    result = activities.run_dcgm_diag({"suite": "2", "incident_id": "inc-real"})
    assert result["ok"] is True
    assert result["diag_pass"] is True
    assert result["mode"] == "mock_fallback"
    assert "real_error" in result


def test_resolve_keep_incident(worker_data, monkeypatch):
    from app import activities

    def fake_http(method, url, *, body=None, headers=None, timeout=30.0):
        assert method == "POST"
        assert "/incidents/inc-9/status" in url
        assert body["status"] == "resolved"
        assert headers["x-api-key"] == "keepappkey"
        return 200, {"id": "inc-9", "status": "resolved"}

    monkeypatch.setattr(activities, "_http_json", fake_http)
    monkeypatch.setenv("KEEP_API_URL", "http://keep.test")
    monkeypatch.setenv("KEEP_API_KEY", "keepappkey")
    result = activities.resolve_keep_incident({"incident_id": "inc-9"})
    assert result["ok"] is True


def test_send_gpu_failure_email(worker_data, monkeypatch):
    from app import activities

    def fake_http(method, url, *, body=None, headers=None, timeout=30.0):
        assert method == "POST"
        assert url.endswith("/gpu/emails")
        assert "failed" in body["subject"].lower() or "GPU" in body["subject"]
        return 200, {"ok": True, "email": {"id": "m1"}}

    monkeypatch.setattr(activities, "_http_json", fake_http)
    result = activities.send_gpu_failure_email(
        {"incident_id": "inc-3", "host": "gpu-node-a03", "error": "boom"}
    )
    assert result["ok"] is True
    assert result["to"] == "ops@ai-dc.local"


def test_request_keep_approval(worker_data, monkeypatch):
    from app import activities

    def fake_http(method, url, *, body=None, headers=None, timeout=30.0):
        assert method == "POST"
        assert url.endswith("/approvals")
        assert body["action_type"] == "temporal_signal"
        assert body["callback"]["kind"] == "temporal_signal"
        assert body["callback"]["workflow_id"] == "wf-1"
        assert headers["x-api-key"] == "keepappkey"
        return 200, {"id": 42, "status": "pending"}

    monkeypatch.setattr(activities, "_http_json", fake_http)
    monkeypatch.setenv("KEEP_API_URL", "http://keep.test")
    result = activities.request_keep_approval(
        {
            "title": "Remediate GPU",
            "workflow_id": "wf-1",
            "run_id": "run-1",
            "incident_id": "inc-1",
            "host": "gpu-node-a03",
            "action": "reset_gpu",
        }
    )
    assert result["ok"] is True
    assert result["http_status"] == 200
    assert result["response"]["id"] == 42
