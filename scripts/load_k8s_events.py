#!/usr/bin/env python3
"""Burst-ingest Keep alerts against a running API (kind local-dev or Compose).

Local kind cannot finish a literal 1M-event run in one sitting. Use this to
measure ingest rate, then extrapolate to 1M/day (~700 events/min average).

  python3 scripts/load_k8s_events.py --count 2000 --concurrency 20 --batch-size 20
  COUNT=1000000 python3 scripts/load_k8s_events.py   # full-day volume (hours)

Does not start services on the host — posts to KEEP_API (default localhost:8080).
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any


def build_alert(
    index: int,
    *,
    run_id: str,
    source: str = "keep",
    severity: str = "warning",
) -> dict[str, Any]:
    """One Keep generic-alert payload. Unique fingerprint unless index is reused."""
    fingerprint = f"scale-{run_id}-{index}"
    return {
        "name": f"scale-event-{index}",
        "message": f"Load-test event {index} ({run_id})",
        "status": "firing",
        "severity": severity,
        "source": [source],
        "fingerprint": fingerprint,
        "labels": {
            "run_id": run_id,
            "event_index": str(index),
            "suite": "load_k8s_events",
        },
    }


def chunked(items: list[Any], size: int) -> list[list[Any]]:
    if size < 1:
        raise ValueError("batch size must be >= 1")
    return [items[i : i + size] for i in range(0, len(items), size)]


def post_events(
    api: str,
    api_key: str,
    payload: list[dict[str, Any]] | dict[str, Any],
    timeout: float,
) -> tuple[int, float, str]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{api.rstrip('/')}/alerts/event",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-key": api_key,
        },
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed = time.perf_counter() - started
            return resp.status, elapsed, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        elapsed = time.perf_counter() - started
        err = exc.read().decode("utf-8", "replace")
        return exc.code, elapsed, err


def get_json(api: str, api_key: str, path: str, timeout: float = 30.0) -> Any:
    req = urllib.request.Request(
        f"{api.rstrip('/')}{path}",
        headers={"Accept": "application/json", "x-api-key": api_key},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def incident_count(api: str, api_key: str) -> int:
    data = get_json(api, api_key, "/incidents?limit=1")
    if isinstance(data, dict) and "count" in data:
        return int(data["count"])
    return -1


def alert_count_post(api: str, api_key: str, timeout: float = 30.0) -> int:
    body = json.dumps({"cel": "", "limit": 1, "offset": 0}).encode("utf-8")
    req = urllib.request.Request(
        f"{api.rstrip('/')}/alerts/query",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-key": api_key,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if isinstance(data, dict) and "count" in data:
        return int(data["count"])
    return -1


def wait_for_digest(
    api: str,
    api_key: str,
    *,
    min_count: int,
    timeout_secs: float,
    poll_secs: float = 3.0,
) -> tuple[int, float, bool]:
    """Poll /alerts/query until count >= min_count or it stops growing."""
    if timeout_secs <= 0:
        return -1, 0.0, False
    started = time.perf_counter()
    last = -1
    stable = 0
    while time.perf_counter() - started < timeout_secs:
        try:
            current = alert_count_post(api, api_key)
        except Exception:  # noqa: BLE001
            time.sleep(poll_secs)
            continue
        if current >= min_count:
            return current, time.perf_counter() - started, True
        if current == last:
            stable += 1
            if stable >= 3 and current > 0:
                return current, time.perf_counter() - started, False
        else:
            stable = 0
            last = current
        time.sleep(poll_secs)
    return last, time.perf_counter() - started, False


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api",
        default=os.environ.get("KEEP_API", os.environ.get("KEEP_API_URL", "http://localhost:8080")),
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("KEEP_API_KEY", "keepappkey"),
    )
    parser.add_argument(
        "--count",
        type=int,
        default=int(os.environ.get("COUNT", "2000")),
        help="Number of events to send (default 2000). 1_000_000 ≈ one target day.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=int(os.environ.get("CONCURRENCY", "20")),
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=int(os.environ.get("BATCH_SIZE", "20")),
    )
    parser.add_argument("--timeout", type=float, default=float(os.environ.get("TIMEOUT", "60")))
    parser.add_argument(
        "--run-id",
        default=os.environ.get("RUN_ID") or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
    )
    parser.add_argument(
        "--wait-digest-secs",
        type=float,
        default=float(os.environ.get("WAIT_DIGEST_SECS", "180")),
        help="Max seconds to wait for digest threads to persist alerts.",
    )
    return parser.parse_args(argv)


def run_load(args: argparse.Namespace) -> dict[str, Any]:
    alerts = [build_alert(i, run_id=args.run_id) for i in range(args.count)]
    batches = chunked(alerts, args.batch_size)
    health = get_json(args.api, args.api_key, "/healthcheck")
    incidents_before = incident_count(args.api, args.api_key)
    alerts_before = alert_count_post(args.api, args.api_key)

    statuses: list[int] = []
    latencies: list[float] = []
    errors = 0
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        futures = [
            pool.submit(post_events, args.api, args.api_key, batch, args.timeout)
            for batch in batches
        ]
        for fut in as_completed(futures):
            status, elapsed, _body = fut.result()
            statuses.append(status)
            latencies.append(elapsed)
            if status >= 400:
                errors += 1
    wall = time.perf_counter() - started
    digest_count, digest_wait, digest_caught_up = wait_for_digest(
        args.api,
        args.api_key,
        min_count=alerts_before + args.count,
        timeout_secs=max(0.0, args.wait_digest_secs),
    )
    incidents_after = incident_count(args.api, args.api_key)
    digest_events = max(0, digest_count - alerts_before)
    digest_per_sec = digest_events / digest_wait if digest_wait else 0.0

    accepted = sum(1 for s in statuses if s < 400)
    events_per_sec = args.count / wall if wall else 0.0
    events_per_min = events_per_sec * 60.0
    summary = {
        "api": args.api,
        "health": health,
        "run_id": args.run_id,
        "count": args.count,
        "batches": len(batches),
        "batch_size": args.batch_size,
        "concurrency": args.concurrency,
        "accepted_batches": accepted,
        "error_batches": errors,
        "wall_seconds": round(wall, 3),
        "events_per_sec": round(events_per_sec, 2),
        "events_per_min": round(events_per_min, 1),
        "hours_for_1m": round(1_000_000 / events_per_sec / 3600, 2) if events_per_sec else None,
        "http_p50_s": round(statistics.median(latencies), 3) if latencies else None,
        "http_p95_s": round(statistics.quantiles(latencies, n=20)[18], 3)
        if len(latencies) >= 20
        else (round(max(latencies), 3) if latencies else None),
        "incidents_before": incidents_before,
        "incidents_after": incidents_after,
        "alerts_before": alerts_before,
        "alerts_after": digest_count,
        "digest_seconds": round(digest_wait, 3),
        "digest_events_per_sec": round(digest_per_sec, 2),
        "digest_events_per_min": round(digest_per_sec * 60.0, 1),
        "digest_caught_up": digest_caught_up,
        "target_1m_per_day_avg_per_min": 694.4,
        "http_accept_meets_avg_1m_day": events_per_min >= 694.4,
        "digest_meets_avg_1m_day": (digest_per_sec * 60.0) >= 694.4,
    }
    return summary


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.count < 1:
        print("count must be >= 1", file=sys.stderr)
        return 2
    try:
        summary = run_load(args)
    except Exception as exc:  # noqa: BLE001 — CLI surface
        print(f"load failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2))
    if summary["error_batches"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
