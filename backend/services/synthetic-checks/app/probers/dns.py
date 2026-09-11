"""DNS resolve prober."""

from __future__ import annotations

import time
from typing import Any

import dns.exception
import dns.resolver

from app.probers.base import probe_result


def probe_dns(target: str, module_config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = module_config or {}
    timeout = float(config.get("timeout_seconds") or config.get("timeout") or 3)
    query_type = str(config.get("query_type") or "A").upper()
    nameserver = config.get("nameserver") or config.get("server")

    start = time.perf_counter()
    try:
        resolver = dns.resolver.Resolver(configure=True)
        resolver.lifetime = timeout
        resolver.timeout = timeout
        if nameserver:
            resolver.nameservers = [str(nameserver)]

        answer = resolver.resolve(target, query_type)
        records = [rdata.to_text() for rdata in answer]
        duration = time.perf_counter() - start
        if not records:
            return probe_result(
                success=False,
                duration_seconds=duration,
                prober="dns",
                target=target,
                error=f"no {query_type} records",
                extra={"query_type": query_type},
            )
        return probe_result(
            success=True,
            duration_seconds=duration,
            prober="dns",
            target=target,
            extra={"query_type": query_type, "records": records},
        )
    except (dns.exception.DNSException, Exception) as exc:
        duration = time.perf_counter() - start
        return probe_result(
            success=False,
            duration_seconds=duration,
            prober="dns",
            target=target,
            error=str(exc),
            extra={"query_type": query_type},
        )
