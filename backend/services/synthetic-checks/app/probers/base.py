"""Shared probe result helpers."""

from __future__ import annotations

from typing import Any


def probe_result(
    *,
    success: bool,
    duration_seconds: float,
    prober: str,
    target: str,
    error: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "success": bool(success),
        "duration_seconds": float(duration_seconds),
        "prober": prober,
        "target": target,
        "error": error,
    }
    if extra:
        result.update(extra)
    return result
