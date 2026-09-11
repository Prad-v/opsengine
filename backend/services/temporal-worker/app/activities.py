"""Activities for the list-and-zip Temporal worker."""

from __future__ import annotations

import os
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from temporalio import activity


@activity.defn
def run_ls(path: str = ".") -> dict[str, Any]:
    """
    Run `ls -la` on the given path and return captured output.

    The path is resolved relative to TEMPORAL_WORKER_ROOT (default /data).
    """
    root = Path(os.environ.get("TEMPORAL_WORKER_ROOT", "/data")).resolve()
    target = (root / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()

    # Prevent escaping the worker root for relative paths.
    if not str(target).startswith(str(root)):
        raise ValueError(f"Path '{path}' is outside worker root '{root}'")
    if not target.exists():
        raise FileNotFoundError(f"Path does not exist: {target}")

    result = subprocess.run(
        ["ls", "-la", str(target)],
        check=False,
        capture_output=True,
        text=True,
    )
    return {
        "path": str(target),
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "listed_at": datetime.now(tz=timezone.utc).isoformat(),
    }


@activity.defn
def create_zip_from_ls(ls_result: dict[str, Any], incident_id: str | None = None) -> dict[str, Any]:
    """
    Write ls output into a zip archive under the worker output directory.

    Returns metadata including the zip file path (inside the container/volume).
    """
    root = Path(os.environ.get("TEMPORAL_WORKER_ROOT", "/data")).resolve()
    output_dir = root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = f"-{incident_id}" if incident_id else ""
    zip_name = f"ls-output{suffix}-{stamp}.zip"
    zip_path = output_dir / zip_name

    listing_name = "ls-output.txt"
    listing_body = (
        f"path: {ls_result.get('path')}\n"
        f"listed_at: {ls_result.get('listed_at')}\n"
        f"exit_code: {ls_result.get('exit_code')}\n\n"
        f"--- stdout ---\n{ls_result.get('stdout') or ''}\n"
        f"--- stderr ---\n{ls_result.get('stderr') or ''}\n"
    )

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(listing_name, listing_body)

    return {
        "zip_path": str(zip_path),
        "zip_name": zip_name,
        "bytes": zip_path.stat().st_size,
        "listing_file": listing_name,
        "incident_id": incident_id,
        "source_path": ls_result.get("path"),
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }
