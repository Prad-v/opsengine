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
