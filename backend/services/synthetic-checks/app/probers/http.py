"""HTTP blackbox-style prober."""

from __future__ import annotations

import re
import time
from typing import Any

import httpx

from app.probers.base import probe_result


def probe_http(target: str, module_config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = module_config or {}
    method = str(config.get("method") or "GET").upper()
    timeout = float(config.get("timeout_seconds") or config.get("timeout") or 5)
    valid_status_codes = config.get("valid_status_codes") or [200]
    headers = dict(config.get("headers") or {})
    body = config.get("body")
    follow_redirects = bool(config.get("follow_redirects", True))
    verify_tls = not bool(config.get("insecure_skip_verify", False))
    fail_if_body_matches = config.get("fail_if_body_matches_regexp")
    fail_if_body_not_matches = config.get("fail_if_body_not_matches_regexp")
    max_duration = config.get("max_duration_seconds")

    request_kwargs: dict[str, Any] = {}
    if isinstance(body, (dict, list)):
        request_kwargs["json"] = body
        headers.setdefault("Content-Type", "application/json")
    elif body is not None:
        request_kwargs["content"] = (
            body if isinstance(body, (bytes, bytearray)) else str(body)
        )
    request_kwargs["headers"] = headers

    start = time.perf_counter()
    try:
        with httpx.Client(
            timeout=timeout,
            follow_redirects=follow_redirects,
            verify=verify_tls,
        ) as client:
            response = client.request(method, target, **request_kwargs)
        duration = time.perf_counter() - start

        if response.status_code not in valid_status_codes:
            return probe_result(
                success=False,
                duration_seconds=duration,
                prober="http",
                target=target,
                error=f"unexpected status code {response.status_code}",
                extra={"status_code": response.status_code},
            )

        text = response.text or ""
        if fail_if_body_matches:
            pattern = re.compile(str(fail_if_body_matches))
            if pattern.search(text):
                return probe_result(
                    success=False,
                    duration_seconds=duration,
                    prober="http",
                    target=target,
                    error="body matched fail_if_body_matches_regexp",
                    extra={"status_code": response.status_code},
                )
        if fail_if_body_not_matches:
            pattern = re.compile(str(fail_if_body_not_matches))
            if not pattern.search(text):
                return probe_result(
                    success=False,
                    duration_seconds=duration,
                    prober="http",
                    target=target,
                    error="body did not match fail_if_body_not_matches_regexp",
                    extra={"status_code": response.status_code},
                )

        if max_duration is not None and duration > float(max_duration):
            return probe_result(
                success=False,
                duration_seconds=duration,
                prober="http",
                target=target,
                error=(
                    f"probe_duration_seconds {duration:.3f} exceeded "
                    f"max_duration_seconds {max_duration}"
                ),
                extra={"status_code": response.status_code},
            )

        return probe_result(
            success=True,
            duration_seconds=duration,
            prober="http",
            target=target,
            extra={"status_code": response.status_code},
        )
    except Exception as exc:
        duration = time.perf_counter() - start
        return probe_result(
            success=False,
            duration_seconds=duration,
            prober="http",
            target=target,
            error=str(exc),
        )
