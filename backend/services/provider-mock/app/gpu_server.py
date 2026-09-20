"""In-memory mock NVIDIA GPU server + failure email inbox for AI DC demos."""

from __future__ import annotations

import time
import uuid
from collections import deque
from typing import Any

from app.gpu_topology import DEFAULT_HOST, default_server_snapshot, get_host, inventory_nodes


DEFAULT_SERVER: dict[str, Any] = default_server_snapshot()


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
            "emails": list(self.emails),
        }

    def set_mode(self, *, force_fail: bool) -> dict[str, Any]:
        self.force_fail = bool(force_fail)
        return {"ok": True, "force_fail": self.force_fail}

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
        self.emails.clear()
        return self.snapshot()


gpu_server = MockGpuServer()
