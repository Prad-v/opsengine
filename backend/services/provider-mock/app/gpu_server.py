"""In-memory mock NVIDIA GPU server + failure email inbox for AI DC demos."""

from __future__ import annotations

import time
import uuid
from collections import deque
from typing import Any

from app.gpu_topology import DEFAULT_HOST, default_server_snapshot, get_host, inventory_nodes


DEFAULT_SERVER: dict[str, Any] = default_server_snapshot()

# Mock suites mirror NVIDIA dcgmi diag levels (see DCGM diagnostics reference).
SUITE_TESTS: dict[str, list[str]] = {
    "1": ["software"],
    "quick": ["software"],
    "short": ["software"],
    "2": ["software", "memory", "pcie"],
    "medium": ["software", "memory", "pcie"],
    "3": [
        "software",
        "memory",
        "pcie",
        "diagnostic",
        "memory_bandwidth",
        "targeted_stress",
        "targeted_power",
    ],
    "long": [
        "software",
        "memory",
        "pcie",
        "diagnostic",
        "memory_bandwidth",
        "targeted_stress",
        "targeted_power",
    ],
    "4": [
        "software",
        "memory",
        "pcie",
        "diagnostic",
        "memory_bandwidth",
        "targeted_stress",
        "targeted_power",
        "memtest",
        "pulse_test",
    ],
    "xlong": [
        "software",
        "memory",
        "pcie",
        "diagnostic",
        "memory_bandwidth",
        "targeted_stress",
        "targeted_power",
        "memtest",
        "pulse_test",
    ],
}

# Alert-code → preferred suite when callers omit suite/run.
CODE_SUITE_HINTS: dict[str, str] = {
    "DCGM_FI_DEV_GPU_TEMP": "1",
    "DCGM_FI_DEV_THERMAL_VIOLATION": "1",
    "DCGM_FI_DEV_POWER_USAGE": "2",
    "DCGM_FI_DEV_FB_USED": "2",
    "DCGM_FI_DEV_XID_ERRORS": "2",
    "DCGM_FI_DEV_ECC_DBE_VOL_TOTAL": "2",
    "DCGM_FI_DEV_NVLINK_CRC_FLIT_ERROR_COUNT_TOTAL": "3",
    "DCGM_EXP_GPU_HEALTH_STATUS": "2",
}


def _normalize_suite(suite: str | None, run: str | None, alert_code: str | None) -> str:
    raw = (suite or run or "").strip().lower().replace(" ", "_")
    if raw in SUITE_TESTS:
        return raw
    if raw and raw not in SUITE_TESTS:
        # Named comma-separated plugin list (e.g. "pcie,memory").
        return raw
    hint = CODE_SUITE_HINTS.get((alert_code or "").strip())
    return hint or "2"


def _tests_for_suite(suite_key: str) -> list[str]:
    if suite_key in SUITE_TESTS:
        return list(SUITE_TESTS[suite_key])
    names = [n.strip() for n in suite_key.split(",") if n.strip()]
    return names or list(SUITE_TESTS["2"])


def _clone_node(host: str | None = None) -> dict[str, Any]:
    try:
        node = get_host(host or DEFAULT_HOST)
    except KeyError:
        node = get_host(DEFAULT_HOST)
    return {
        "host": node["host"],
        "region": node["region"],
        "datacenter": node["datacenter"],
        "row": node["row"],
        "rack": node["rack"],
        "cluster": node["cluster"],
        "vendor": node["vendor"],
        "gpu_model": node["gpu_model"],
        "namespace": node["namespace"],
        "gpus": [
            {
                "index": gpu["index"],
                "uuid": gpu["uuid"],
                "health": "ok",
                "temperature_c": 62.0,
                "memory_util_pct": 41.0,
                "xid": None,
            }
            for gpu in node["gpus"]
        ],
        "cordoned": False,
        "drained": False,
    }


class MockGpuServer:
    """Stateful mock for Temporal remediations against NVIDIA GPU nodes."""

    def __init__(self) -> None:
        self.force_fail = False
        self.nodes: dict[str, dict[str, Any]] = {
            item["host"]: _clone_node(item["host"]) for item in inventory_nodes()
        }
        self.server: dict[str, Any] = self.nodes[DEFAULT_HOST]
        self.remediations: deque[dict[str, Any]] = deque(maxlen=50)
        self.diagnostics: deque[dict[str, Any]] = deque(maxlen=50)
        self.lifecycle: deque[dict[str, Any]] = deque(maxlen=50)
        self.emails: deque[dict[str, Any]] = deque(maxlen=50)

    def _node(self, host: str | None) -> dict[str, Any]:
        key = host or DEFAULT_HOST
        if key not in self.nodes:
            self.nodes[key] = _clone_node(key)
        if key == DEFAULT_HOST:
            self.server = self.nodes[key]
        return self.nodes[key]

    def snapshot(self) -> dict[str, Any]:
        return {
            "force_fail": self.force_fail,
            "server": self.server,
            "nodes": list(self.nodes.values()),
            "remediations": list(self.remediations),
            "diagnostics": list(self.diagnostics),
            "lifecycle": list(self.lifecycle),
            "emails": list(self.emails),
        }

    def set_mode(self, *, force_fail: bool) -> dict[str, Any]:
        self.force_fail = bool(force_fail)
        return {"ok": True, "force_fail": self.force_fail}

    def cordon(
        self,
        *,
        host: str | None = None,
        drain: bool = True,
        incident_id: str | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Mark a node unschedulable (and optionally drained) before L2+ diag."""
        node = self._node(host)
        node["cordoned"] = True
        if drain:
            node["drained"] = True
        entry: dict[str, Any] = {
            "id": uuid.uuid4().hex[:12],
            "ts": time.time(),
            "action": "cordon",
            "host": node["host"],
            "cordoned": True,
            "drained": bool(node.get("drained")),
            "incident_id": incident_id,
            "reason": reason or "dcgm_diag",
            "ok": True,
            "message": (
                f"Cordoned {node['host']}"
                + (" and drained workloads" if drain else "")
                + f" ({reason or 'dcgm_diag'})."
            ),
        }
        self.lifecycle.appendleft(entry)
        return entry

    def uncordon(
        self,
        *,
        host: str | None = None,
        incident_id: str | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        node = self._node(host)
        node["cordoned"] = False
        node["drained"] = False
        entry: dict[str, Any] = {
            "id": uuid.uuid4().hex[:12],
            "ts": time.time(),
            "action": "uncordon",
            "host": node["host"],
            "cordoned": False,
            "drained": False,
            "incident_id": incident_id,
            "reason": reason or "diag_complete",
            "ok": True,
            "message": (
                f"Uncordoned {node['host']} "
                f"({reason or 'diag_complete'})."
            ),
        }
        self.lifecycle.appendleft(entry)
        return entry

    def remediate(
        self,
        *,
        action: str = "reset_gpu",
        gpu_index: int = 0,
        incident_id: str | None = None,
        alertname: str | None = None,
        host: str | None = None,
    ) -> dict[str, Any]:
        node = self._node(host)
        ts = time.time()
        entry: dict[str, Any] = {
            "id": uuid.uuid4().hex[:12],
            "ts": ts,
            "action": action,
            "gpu_index": gpu_index,
            "incident_id": incident_id,
            "alertname": alertname,
            "host": node["host"],
            "region": node.get("region"),
            "datacenter": node.get("datacenter"),
            "row": node.get("row"),
            "rack": node.get("rack"),
        }

        if self.force_fail:
            entry["ok"] = False
            entry["error"] = (
                f"Mock remediation '{action}' failed on {node['host']} "
                f"(force_fail=true)."
            )
            self.remediations.appendleft(entry)
            for gpu in node["gpus"]:
                if gpu["index"] == gpu_index:
                    gpu["health"] = "fail"
                    gpu["xid"] = 79
            return entry

        if action == "isolate_gpu":
            for gpu in node["gpus"]:
                if gpu["index"] == gpu_index:
                    gpu["health"] = "isolated"
                    gpu["xid"] = gpu.get("xid") or 79
            entry["ok"] = True
            entry["message"] = (
                f"Isolation '{action}' recorded on {node['host']} "
                f"{node.get('row')}/{node.get('rack')} gpu={gpu_index} "
                f"({node['gpu_model']})."
            )
            self.remediations.appendleft(entry)
            return entry

        for gpu in node["gpus"]:
            if gpu["index"] == gpu_index:
                gpu["health"] = "ok"
                gpu["temperature_c"] = 58.0
                gpu["memory_util_pct"] = 35.0
                gpu["xid"] = None
        entry["ok"] = True
        entry["message"] = (
            f"Remediation '{action}' succeeded on {node['host']} "
            f"{node.get('row')}/{node.get('rack')} gpu={gpu_index} "
            f"({node['gpu_model']})."
        )
        self.remediations.appendleft(entry)
        return entry

    def diag(
        self,
        *,
        suite: str | None = None,
        run: str | None = None,
        gpu_index: int = 0,
        incident_id: str | None = None,
        alertname: str | None = None,
        alert_code: str | None = None,
        host: str | None = None,
    ) -> dict[str, Any]:
        """
        Mock ``dcgmi diag --run`` against an inventory GPU.

        Always returns HTTP-friendly structured results (ok=True for transport).
        Product branching uses ``result`` / ``recommendation`` / ``severity``.
        """
        node = self._node(host)
        suite_key = _normalize_suite(suite, run, alert_code)
        tests = _tests_for_suite(suite_key)
        ts = time.time()
        entry: dict[str, Any] = {
            "id": uuid.uuid4().hex[:12],
            "ts": ts,
            "host": node["host"],
            "region": node.get("region"),
            "datacenter": node.get("datacenter"),
            "row": node.get("row"),
            "rack": node.get("rack"),
            "gpu_index": gpu_index,
            "incident_id": incident_id,
            "alertname": alertname,
            "alert_code": alert_code,
            "suite": suite_key,
            "ok": True,  # transport success; see result/recommendation
        }

        if self.force_fail:
            failed_test = "memory" if "memory" in tests else tests[-1]
            plugin_results = [
                {
                    "name": name,
                    "status": "Fail" if name == failed_test else "Pass",
                    "detail": (
                        f"Mock {name} failed (force_fail=true)."
                        if name == failed_test
                        else None
                    ),
                }
                for name in tests
            ]
            entry.update(
                {
                    "result": "Fail",
                    "recommendation": "ISOLATE",
                    "severity": "ISOLATE",
                    "error_code": "DCGM_FR_FAULTY_MEMORY",
                    "error_category": "DCGM_FR_EC_HARDWARE_MEMORY",
                    "tests": plugin_results,
                    "message": (
                        f"DCGM diag suite={suite_key} failed on {node['host']} "
                        f"gpu={gpu_index}: {failed_test} (force_fail=true). "
                        "Isolate the GPU; do not auto-reset."
                    ),
                }
            )
            for gpu in node["gpus"]:
                if gpu["index"] == gpu_index:
                    gpu["health"] = "fail"
                    gpu["xid"] = 79
            self.diagnostics.appendleft(entry)
            return entry

        plugin_results = [
            {"name": name, "status": "Pass", "detail": None} for name in tests
        ]
        entry.update(
            {
                "result": "Pass",
                "recommendation": "RESET",
                "severity": "NONE",
                "error_code": None,
                "error_category": None,
                "tests": plugin_results,
                "message": (
                    f"DCGM diag suite={suite_key} passed on {node['host']} "
                    f"{node.get('row')}/{node.get('rack')} gpu={gpu_index}. "
                    "Safe to reset_gpu."
                ),
            }
        )
        self.diagnostics.appendleft(entry)
        return entry

    def add_email(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        incident_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        mail = {
            "id": uuid.uuid4().hex[:12],
            "ts": time.time(),
            "to": to,
            "subject": subject,
            "body": body,
            "incident_id": incident_id,
            "metadata": metadata or {},
        }
        self.emails.appendleft(mail)
        return mail

    def clear_emails(self) -> None:
        self.emails.clear()

    def reset(self) -> dict[str, Any]:
        self.force_fail = False
        self.nodes = {item["host"]: _clone_node(item["host"]) for item in inventory_nodes()}
        self.server = self.nodes[DEFAULT_HOST]
        self.remediations.clear()
        self.diagnostics.clear()
        self.lifecycle.clear()
        self.emails.clear()
        return self.snapshot()


gpu_server = MockGpuServer()
