"""TCP connect prober."""

from __future__ import annotations

import socket
import time
from typing import Any
from urllib.parse import urlparse

from app.probers.base import probe_result


def _parse_host_port(target: str, default_port: int | None) -> tuple[str, int]:
    raw = target.strip()
    if "://" in raw:
        parsed = urlparse(raw)
        host = parsed.hostname or raw
        port = parsed.port or default_port
    elif raw.count(":") == 1 and not raw.startswith("["):
        host, port_str = raw.rsplit(":", 1)
        host = host.strip()
        port = int(port_str)
    else:
        host = raw
        port = default_port

    if not host or port is None:
        raise ValueError(
            f"TCP target '{target}' must include host:port or module_config.port"
        )
    return host, int(port)


def probe_tcp(target: str, module_config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = module_config or {}
    timeout = float(config.get("timeout_seconds") or config.get("timeout") or 3)
    default_port = config.get("port")
    if default_port is not None:
        default_port = int(default_port)

    start = time.perf_counter()
    try:
        host, port = _parse_host_port(target, default_port)
        with socket.create_connection((host, port), timeout=timeout):
            pass
        duration = time.perf_counter() - start
        return probe_result(
            success=True,
            duration_seconds=duration,
            prober="tcp",
            target=target,
            extra={"host": host, "port": port},
        )
    except Exception as exc:
        duration = time.perf_counter() - start
        return probe_result(
            success=False,
            duration_seconds=duration,
            prober="tcp",
            target=target,
            error=str(exc),
        )
