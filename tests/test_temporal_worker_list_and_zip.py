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
