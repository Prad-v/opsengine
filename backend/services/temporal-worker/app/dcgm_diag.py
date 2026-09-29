"""DCGM diagnostic helpers for suite policy and optional real ``dcgmi`` runs."""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any


SUITE_LEVEL: dict[str, int] = {
    "1": 1,
    "quick": 1,
    "short": 1,
    "2": 2,
    "medium": 2,
    "3": 3,
    "long": 3,
    "4": 4,
    "xlong": 4,
    "production_testing": 3,
}


def normalize_suite_key(
    suite: str | None = None,
    run: str | None = None,
) -> str:
    raw = (suite or run or "2").strip().lower().replace(" ", "_")
    return raw or "2"


def suite_level(suite: str | None = None, run: str | None = None) -> int:
    """Map suite selector to numeric level (1–4). Named plugins default to 2."""
    key = normalize_suite_key(suite, run)
    if key in SUITE_LEVEL:
        return SUITE_LEVEL[key]
    # Comma-separated named plugins → treat as medium (cordon, no auto-approval).
    return 2


def requires_cordon(level: int) -> bool:
    """L2+ diagnostics contend with workloads — cordon/drain first."""
    return level >= 2


def requires_approval(level: int) -> bool:
    """L3+ (long / xlong) require human approval by default."""
    return level >= 3


def parse_dcgmi_json(
    raw: str | dict[str, Any],
    *,
    suite: str,
    host: str,
    gpu_index: int,
) -> dict[str, Any]:
    """
    Best-effort normalize ``dcgmi diag --json`` into the mock-compatible shape.

    NVIDIA does not publish a stable JSON schema; pin DCGM versions in production.
    """
    data: Any = raw
    if isinstance(raw, str):
        data = json.loads(raw)

    tests: list[dict[str, Any]] = []
    overall = "Pass"
    error_code: str | None = None
    error_category: str | None = None
    severity = "NONE"
    messages: list[str] = []

    # Common shapes observed across DCGM releases: top-level test map, or
    # { "DCGM Diagnostic": { "test_categories": [...] } }.
    categories = None
    if isinstance(data, dict):
        categories = (
            data.get("test_categories")
            or (data.get("DCGM Diagnostic") or {}).get("test_categories")
            or data.get("tests")
        )
        if isinstance(data.get("Overall Health"), str):
            overall_hint = str(data["Overall Health"]).lower()
            if overall_hint in {"fail", "failed", "error"}:
                overall = "Fail"

    if isinstance(categories, list):
        for cat in categories:
            if not isinstance(cat, dict):
                continue
            name = (
                cat.get("category")
                or cat.get("test_name")
                or cat.get("name")
                or "unknown"
            )
            status_raw = (
                cat.get("status")
                or cat.get("result")
                or cat.get("Status")
                or "Pass"
            )
            status = str(status_raw).capitalize()
            if status.lower() in {"fail", "failed", "error"}:
                status = "Fail"
                overall = "Fail"
            elif status.lower() in {"skip", "skipped"}:
                status = "Skip"
            else:
                status = "Pass"
            detail = cat.get("message") or cat.get("info") or cat.get("warnings")
            tests.append({"name": str(name), "status": status, "detail": detail})
            errs = cat.get("error_code") or cat.get("errors")
            if isinstance(errs, str) and errs.startswith("DCGM_FR_"):
                error_code = errs
            elif isinstance(errs, list) and errs:
                first = errs[0]
                if isinstance(first, dict):
                    error_code = first.get("code") or error_code
                    error_category = first.get("category") or error_category
                    messages.append(str(first.get("message") or ""))
                elif isinstance(first, str):
                    error_code = first if first.startswith("DCGM_FR_") else error_code

    if not tests and isinstance(data, dict):
        # Flat plugin map: { "memory": { "status": "Pass" }, ... }
        for key, val in data.items():
            if not isinstance(val, dict):
                continue
            if "status" not in val and "result" not in val:
                continue
            status_raw = val.get("status") or val.get("result") or "Pass"
            status = str(status_raw).capitalize()
            if status.lower() in {"fail", "failed"}:
                status = "Fail"
                overall = "Fail"
            tests.append(
                {
                    "name": str(key),
                    "status": status,
                    "detail": val.get("message") or val.get("info"),
                }
            )

    if overall == "Fail":
        recommendation = "ISOLATE"
        severity = "ISOLATE"
        if not error_code:
            error_code = "DCGM_FR_UNKNOWN"
    else:
        recommendation = "RESET"
        severity = "NONE"

    message = (
        "; ".join(m for m in messages if m)
        or f"dcgmi diag suite={suite} on {host} gpu={gpu_index}: {overall}"
    )
    return {
        "ok": True,
        "result": overall,
        "recommendation": recommendation,
        "severity": severity,
        "error_code": error_code,
        "error_category": error_category,
        "tests": tests,
        "suite": suite,
        "host": host,
        "gpu_index": gpu_index,
        "message": message,
        "mode": "real",
        "raw": data if isinstance(data, (dict, list)) else None,
    }


def run_dcgmi_cli(
    *,
    suite: str,
    gpu_index: int = 0,
    host: str = "localhost",
    timeout_sec: int = 600,
    dcgmi_bin: str | None = None,
) -> dict[str, Any]:
    """
    Execute ``dcgmi diag --run … --json`` on the worker host.

    Returns mock-compatible result dict. On missing binary or launch failure,
    returns ok=False with error detail (caller may fall back to mock).
    """
    binary = dcgmi_bin or shutil.which("dcgmi")
    if not binary:
        return {
            "ok": False,
            "diag_pass": False,
            "recommendation": "ISOLATE",
            "error": "dcgmi binary not found on PATH",
            "mode": "real",
            "suite": suite,
            "host": host,
            "gpu_index": gpu_index,
        }

    entity = f"gpu:{gpu_index}"
    cmd = [
        binary,
        "diag",
        "--run",
        suite,
        "--entity-id",
        entity,
        "--json",
        "--timeout",
        str(max(1, int(timeout_sec))),
    ]
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_sec + 30,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "diag_pass": False,
            "recommendation": "ISOLATE",
            "error": f"dcgmi diag timed out after {timeout_sec}s",
            "mode": "real",
            "suite": suite,
            "host": host,
            "gpu_index": gpu_index,
            "command": cmd,
        }
    except OSError as exc:
        return {
            "ok": False,
            "diag_pass": False,
            "recommendation": "ISOLATE",
            "error": f"dcgmi launch failed: {exc}",
            "mode": "real",
            "suite": suite,
            "host": host,
            "gpu_index": gpu_index,
            "command": cmd,
        }

    stdout = (proc.stdout or "").strip()
    # Exit 226 = diagnostic reported error (still parseable JSON on many releases).
    if not stdout:
        return {
            "ok": False,
            "diag_pass": False,
            "recommendation": "ISOLATE",
            "error": proc.stderr or f"dcgmi exited {proc.returncode} with empty stdout",
            "mode": "real",
            "suite": suite,
            "host": host,
            "gpu_index": gpu_index,
            "exit_code": proc.returncode,
            "command": cmd,
        }

    try:
        parsed = parse_dcgmi_json(
            stdout, suite=suite, host=host, gpu_index=gpu_index
        )
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return {
            "ok": False,
            "diag_pass": False,
            "recommendation": "ISOLATE",
            "error": f"failed to parse dcgmi JSON: {exc}",
            "mode": "real",
            "suite": suite,
            "host": host,
            "gpu_index": gpu_index,
            "exit_code": proc.returncode,
            "stdout_preview": stdout[:500],
            "command": cmd,
        }

    parsed["exit_code"] = proc.returncode
    parsed["command"] = cmd
    parsed["diag_pass"] = str(parsed.get("result") or "").lower() == "pass"
    parsed["stderr"] = (proc.stderr or "")[:1000] or None
    return parsed
