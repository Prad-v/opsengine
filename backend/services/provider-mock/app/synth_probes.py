"""Mock AI-datacenter synthetic probe endpoints + Keep check catalog.

HTTP/TCP synthetics in Keep hit these provider-mock paths. Toggle `failed`
per probe from the mock UI to exercise Keep alerts without real GPUs.
"""

from __future__ import annotations

import copy
import time
from typing import Any
from urllib.parse import urlparse

DEFAULT_LABELS = {
    "region": "us-west-2",
    "datacenter": "ai-dc-1",
    "cluster": "ai-dc-prod",
    "source": "synthetic-checks",
}

NVIDIA_LABELS = {
    **DEFAULT_LABELS,
    "vendor": "nvidia",
    "gpu_model": "NVIDIA-H100-80GB-HBM3",
    "host": "gpu-node-a03",
    "row": "row-a",
    "rack": "rack-12",
    "service": "gpu-inference",
}

AMD_LABELS = {
    **DEFAULT_LABELS,
    "vendor": "amd",
    "gpu_model": "AMD-MI300X-192GB",
    "host": "gpu-node-mi300-a01",
    "row": "row-c",
    "rack": "rack-31",
    "service": "gpu-inference",
}

TRAINING_NVIDIA_LABELS = {
    **NVIDIA_LABELS,
    "service": "gpu-training",
    "workload": "training",
}

TRAINING_AMD_LABELS = {
    **AMD_LABELS,
    "service": "gpu-training",
    "workload": "training",
}

# Probe id → human metadata (UI + catalog). Paths are relative to the mock.
PROBE_SPECS: list[dict[str, Any]] = [
    {
        "id": "dc-control-plane",
        "group": "fabric",
        "name": "AI DC control plane TCP",
        "description": "TCP connect to the mock control-plane port (stand-in for kube-apiserver / BMC).",
        "method": "TCP",
        "path": None,
        "code": "SYNTH_DC_CONTROL_PLANE",
    },
    {
        "id": "nvidia-dcgm",
        "group": "nvidia",
        "name": "NVIDIA DCGM exporter",
        "description": "HTTP scrape of mock DCGM metrics (DCGM_FI_DEV_GPU_TEMP present).",
        "method": "GET",
        "path": "/api/synth/nvidia/dcgm/metrics",
        "code": "SYNTH_NVIDIA_DCGM",
    },
    {
        "id": "nvidia-nvml",
        "group": "nvidia",
        "name": "NVIDIA NVML device count",
        "description": "HTTP wrapper around nvidia-smi / NVML device enumeration.",
        "method": "GET",
        "path": "/api/synth/nvidia/nvml",
        "code": "SYNTH_NVIDIA_NVML",
    },
    {
        "id": "nvidia-inference-health",
        "group": "nvidia-inference",
        "name": "NVIDIA inference gateway",
        "description": "Triton/NIM/vLLM front-door /health.",
        "method": "GET",
        "path": "/api/synth/nvidia/inference/health",
        "code": "SYNTH_NVIDIA_INFERENCE_GATEWAY",
    },
    {
        "id": "nvidia-inference-ready",
        "group": "nvidia-inference",
        "name": "NVIDIA inference model ready",
        "description": "Triton /v2/health/ready — model loaded and serving.",
        "method": "GET",
        "path": "/api/synth/nvidia/inference/v2/health/ready",
        "code": "SYNTH_NVIDIA_INFERENCE_READY",
    },
    {
        "id": "nvidia-inference-golden",
        "group": "nvidia-inference",
        "name": "NVIDIA inference golden prompt",
        "description": "POST /v1/chat/completions with a fixed prompt; body must contain the canary string.",
        "method": "POST",
        "path": "/api/synth/nvidia/inference/v1/chat/completions",
        "code": "SYNTH_NVIDIA_INFERENCE_GOLDEN",
    },
    {
        "id": "nvidia-nccl",
        "group": "nvidia-training",
        "name": "NVIDIA NCCL allreduce canary",
        "description": "8-GPU NCCL allreduce smoke (NVLink / IB fabric).",
        "method": "GET",
        "path": "/api/synth/nvidia/nccl/allreduce",
        "code": "SYNTH_NVIDIA_NCCL",
    },
    {
        "id": "amd-rocm",
        "group": "amd",
        "name": "AMD ROCm device count",
        "description": "HTTP wrapper around rocm-smi device enumeration.",
        "method": "GET",
        "path": "/api/synth/amd/rocm",
        "code": "SYNTH_AMD_ROCM",
    },
    {
        "id": "amd-inference-health",
        "group": "amd-inference",
        "name": "AMD inference gateway",
        "description": "vLLM/SGLang on ROCm /health.",
        "method": "GET",
        "path": "/api/synth/amd/inference/health",
        "code": "SYNTH_AMD_INFERENCE_GATEWAY",
    },
    {
        "id": "amd-inference-golden",
        "group": "amd-inference",
        "name": "AMD inference golden prompt",
        "description": "POST /v1/chat/completions on the AMD serving path.",
        "method": "POST",
        "path": "/api/synth/amd/inference/v1/chat/completions",
        "code": "SYNTH_AMD_INFERENCE_GOLDEN",
    },
    {
        "id": "amd-rccl",
        "group": "amd-training",
        "name": "AMD RCCL allreduce canary",
        "description": "8-GPU RCCL allreduce smoke (xGMI / IB fabric).",
        "method": "GET",
        "path": "/api/synth/amd/rccl/allreduce",
        "code": "SYNTH_AMD_RCCL",
    },
    {
        "id": "training-submit",
        "group": "training",
        "name": "Training job submit canary",
        "description": "Submit a 1-GPU canary job through the scheduler API.",
        "method": "POST",
        "path": "/api/synth/training/submit",
        "code": "SYNTH_TRAINING_SUBMIT",
    },
    {
        "id": "training-checkpoint",
        "group": "training",
        "name": "Training checkpoint I/O",
        "description": "Write/read a small checkpoint on the training filesystem.",
        "method": "POST",
        "path": "/api/synth/training/checkpoint",
        "code": "SYNTH_CHECKPOINT_IO",
    },
    {
        "id": "storage-health",
        "group": "fabric",
        "name": "Object store / checkpoint bucket",
        "description": "S3/MinIO gateway health for model artifacts and checkpoints.",
        "method": "GET",
        "path": "/api/synth/storage/health",
        "code": "SYNTH_STORAGE",
    },
    {
        "id": "netbox-dcim",
        "group": "fabric",
        "name": "NetBox DCIM health",
        "description": "Inventory/DCIM API used to seed GPU topology.",
        "method": "GET",
        "path": "/api/synth/netbox/health",
        "code": "SYNTH_DCIM",
    },
]

SYNTH_ALERT_CODES: tuple[dict[str, str], ...] = tuple(
    {
        "code": spec["code"],
        "name": spec["name"],
        "description": spec["description"],
    }
    for spec in PROBE_SPECS
)

GOLDEN_PROMPT = "Keep synthetic canary — reply with the exact token SYNTH_OK."
GOLDEN_COMPLETION = "SYNTH_OK"


class SynthProbeState:
    """In-memory fail flags and last probe hits."""

    def __init__(self) -> None:
        self.failed: set[str] = set()
        self.latency_ms: dict[str, int] = {}
        self.hits: list[dict[str, Any]] = []

    def reset(self) -> dict[str, Any]:
        self.failed.clear()
        self.latency_ms.clear()
        self.hits.clear()
        return self.snapshot()

    def set_failed(self, probe_id: str, failed: bool) -> dict[str, Any]:
        if failed:
            self.failed.add(probe_id)
        else:
            self.failed.discard(probe_id)
        return self.snapshot()

    def set_failed_many(self, flags: dict[str, bool]) -> dict[str, Any]:
        for probe_id, failed in flags.items():
            self.set_failed(probe_id, bool(failed))
        return self.snapshot()

    def is_failed(self, probe_id: str) -> bool:
        return probe_id in self.failed

    def record(self, probe_id: str, ok: bool) -> None:
        self.hits.append(
            {
                "ts": time.time(),
                "probe_id": probe_id,
                "ok": ok,
                "failed_flag": probe_id in self.failed,
            }
        )
        self.hits = self.hits[-50:]

    def maybe_sleep(self, probe_id: str) -> None:
        delay = int(self.latency_ms.get(probe_id) or 0)
        if delay > 0:
            time.sleep(delay / 1000.0)

    def snapshot(self) -> dict[str, Any]:
        probes = []
        for spec in PROBE_SPECS:
            probes.append(
                {
                    **spec,
                    "failed": spec["id"] in self.failed,
                    "latency_ms": int(self.latency_ms.get(spec["id"]) or 0),
                }
            )
        return {
            "failed": sorted(self.failed),
            "probes": probes,
            "hits": list(reversed(self.hits)),
        }


synth_probes = SynthProbeState()


def _spec(probe_id: str) -> dict[str, Any]:
    for item in PROBE_SPECS:
        if item["id"] == probe_id:
            return item
    raise KeyError(probe_id)


def _json_ok(probe_id: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any] | str, str]:
    synth_probes.maybe_sleep(probe_id)
    failed = synth_probes.is_failed(probe_id)
    synth_probes.record(probe_id, not failed)
    if failed:
        return 503, {"ok": False, "probe_id": probe_id, "error": "forced failure"}, "application/json"
    body = {"ok": True, "probe_id": probe_id, **payload}
    return 200, body, "application/json"


def handle_nvidia_dcgm() -> tuple[int, dict[str, Any] | str, str]:
    probe_id = "nvidia-dcgm"
    synth_probes.maybe_sleep(probe_id)
    failed = synth_probes.is_failed(probe_id)
    synth_probes.record(probe_id, not failed)
    if failed:
        text = "# HELP DCGM_FI_DEV_FB_USED framebuffer used.\n# no temperature series\n"
        return 200, text, "text/plain; charset=utf-8"
    text = (
        "# HELP DCGM_FI_DEV_GPU_TEMP GPU temperature (in C).\n"
        "# TYPE DCGM_FI_DEV_GPU_TEMP gauge\n"
        'DCGM_FI_DEV_GPU_TEMP{gpu="0",UUID="GPU-a03-0",device="nvidia0"} 62\n'
        "# HELP DCGM_FI_DEV_FB_USED Framebuffer memory used (in MiB).\n"
        "# TYPE DCGM_FI_DEV_FB_USED gauge\n"
        'DCGM_FI_DEV_FB_USED{gpu="0",UUID="GPU-a03-0"} 18432\n'
    )
    return 200, text, "text/plain; charset=utf-8"


def handle_nvidia_nvml() -> tuple[int, dict[str, Any] | str, str]:
    probe_id = "nvidia-nvml"
    synth_probes.maybe_sleep(probe_id)
    failed = synth_probes.is_failed(probe_id)
    synth_probes.record(probe_id, not failed)
    if failed:
        return 200, {"ok": False, "vendor": "nvidia", "device_count": 0}, "application/json"
    return (
        200,
        {
            "ok": True,
            "vendor": "nvidia",
            "device_count": 8,
            "driver": "550.90.07",
            "gpus": [f"GPU-a03-{i}" for i in range(8)],
        },
        "application/json",
    )


def handle_amd_rocm() -> tuple[int, dict[str, Any] | str, str]:
    probe_id = "amd-rocm"
    synth_probes.maybe_sleep(probe_id)
    failed = synth_probes.is_failed(probe_id)
    synth_probes.record(probe_id, not failed)
    if failed:
        return 200, {"ok": False, "vendor": "amd", "device_count": 0}, "application/json"
    return (
        200,
        {
            "ok": True,
            "vendor": "amd",
            "device_count": 8,
            "rocm": "6.2.0",
            "gpus": [f"GPU-mi300-{i}" for i in range(8)],
        },
        "application/json",
    )


def handle_inference_health(probe_id: str, vendor: str) -> tuple[int, dict[str, Any] | str, str]:
    return _json_ok(probe_id, {"vendor": vendor, "status": "ok", "role": "gateway"})


def handle_inference_ready() -> tuple[int, dict[str, Any] | str, str]:
    return _json_ok(
        "nvidia-inference-ready",
        {"vendor": "nvidia", "ready": True, "models": ["llama-70b", "embed-v1"]},
    )


def handle_golden_prompt(probe_id: str, vendor: str) -> tuple[int, dict[str, Any] | str, str]:
    synth_probes.maybe_sleep(probe_id)
    failed = synth_probes.is_failed(probe_id)
    synth_probes.record(probe_id, not failed)
    content = "model unavailable" if failed else GOLDEN_COMPLETION
    status = 200
    body = {
        "id": f"chatcmpl-{probe_id}",
        "object": "chat.completion",
        "model": "llama-70b" if vendor == "nvidia" else "llama-70b-rocm",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 2, "total_tokens": 14},
        "ok": not failed,
        "probe_id": probe_id,
        "vendor": vendor,
    }
    return status, body, "application/json"


def handle_collective(probe_id: str, vendor: str, collective: str) -> tuple[int, dict[str, Any] | str, str]:
    synth_probes.maybe_sleep(probe_id)
    failed = synth_probes.is_failed(probe_id)
    synth_probes.record(probe_id, not failed)
    if failed:
        return (
            200,
            {
                "ok": False,
                "vendor": vendor,
                "collective": collective,
                "gpus": 8,
                "error": f"{collective} timeout on rank 3",
            },
            "application/json",
        )
    return (
        200,
        {
            "ok": True,
            "vendor": vendor,
            "collective": collective,
            "gpus": 8,
            "busbw_gbs": 320.4 if vendor == "nvidia" else 280.1,
            "algo_ms": 12.4,
        },
        "application/json",
    )


def handle_training_submit() -> tuple[int, dict[str, Any] | str, str]:
    synth_probes.maybe_sleep("training-submit")
    failed = synth_probes.is_failed("training-submit")
    synth_probes.record("training-submit", not failed)
    if failed:
        return (
            200,
            {
                "ok": False,
                "job_id": "canary-1gpu",
                "state": "Pending",
                "gpus": 1,
                "queue": "canary",
                "error": "insufficient GPU quota",
            },
            "application/json",
        )
    return (
        200,
        {
            "ok": True,
            "job_id": "canary-1gpu",
            "state": "Running",
            "gpus": 1,
            "queue": "canary",
            "namespace": "ai-dc-canary",
        },
        "application/json",
    )


def handle_checkpoint() -> tuple[int, dict[str, Any] | str, str]:
    return _json_ok(
        "training-checkpoint",
        {
            "bytes": 1073741824,
            "path": "s3://ai-dc-canary/ckpt.bin",
            "write_ms": 420,
            "read_ms": 310,
        },
    )


def handle_storage() -> tuple[int, dict[str, Any] | str, str]:
    return _json_ok(
        "storage-health",
        {"backend": "s3", "bucket": "ai-dc-canary", "first_byte_ms": 14},
    )


def handle_netbox() -> tuple[int, dict[str, Any] | str, str]:
    return _json_ok("netbox-dcim", {"dcim": "nvidia", "status": "ok"})


def _tcp_target(base_url: str) -> str:
    parsed = urlparse(base_url)
    host = parsed.hostname or "host.docker.internal"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return f"{host}:{port}"


def _http_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}{path}"


def _common_check(
    *,
    spec: dict[str, Any],
    temporal_provider_id: str,
    labels: dict[str, str],
    prober: str,
    targets: list[str],
    interval_seconds: int,
    module_config: dict[str, Any],
) -> dict[str, Any]:
    merged = {**labels, "code": spec["code"], "workload": labels.get("workload") or spec["group"]}
    return {
        "check_key": spec["id"],
        "name": spec["name"],
        "description": spec["description"],
        "prober": prober,
        "module_config": module_config,
        "targets": targets,
        "interval_seconds": interval_seconds,
        "labels": merged,
        "task_queue": "keep-synth",
        "temporal_provider_id": temporal_provider_id,
        "enabled": True,
    }


def build_keep_synthetic_checks(
    base_url: str,
    temporal_provider_id: str,
) -> list[dict[str, Any]]:
    """Keep Mode-1 synthetic check payloads targeting this mock."""
    base = base_url.rstrip("/")
    tcp = _tcp_target(base)
    checks: list[dict[str, Any]] = []

    checks.append(
        _common_check(
            spec=_spec("dc-control-plane"),
            temporal_provider_id=temporal_provider_id,
            labels={**DEFAULT_LABELS, "service": "ai-dc-1", "workload": "fabric"},
            prober="tcp",
            targets=[tcp],
            interval_seconds=60,
            module_config={"timeout_seconds": 3},
        )
    )

    nvidia_http = [
        (
            "nvidia-dcgm",
            NVIDIA_LABELS,
            60,
            {
                "method": "GET",
                "timeout_seconds": 5,
                "valid_status_codes": [200],
                "fail_if_body_not_matches_regexp": "DCGM_FI_DEV_GPU_TEMP",
            },
        ),
        (
            "nvidia-nvml",
            NVIDIA_LABELS,
            60,
            {
                "method": "GET",
                "timeout_seconds": 5,
                "valid_status_codes": [200],
                "fail_if_body_not_matches_regexp": '"device_count": 8',
            },
        ),
        (
            "nvidia-inference-health",
            {**NVIDIA_LABELS, "workload": "inference"},
            30,
            {
                "method": "GET",
                "timeout_seconds": 5,
                "valid_status_codes": [200],
                "fail_if_body_not_matches_regexp": '"ok": true',
            },
        ),
        (
            "nvidia-inference-ready",
            {**NVIDIA_LABELS, "workload": "inference"},
            30,
            {
                "method": "GET",
                "timeout_seconds": 5,
                "valid_status_codes": [200],
                "fail_if_body_not_matches_regexp": '"ready": true',
            },
        ),
        (
            "nvidia-inference-golden",
            {**NVIDIA_LABELS, "workload": "inference"},
            30,
            {
                "method": "POST",
                "timeout_seconds": 8,
                "max_duration_seconds": 2,
                "valid_status_codes": [200],
                "headers": {"Content-Type": "application/json"},
                "body": {
                    "model": "llama-70b",
                    "messages": [{"role": "user", "content": GOLDEN_PROMPT}],
                    "max_tokens": 8,
                },
                "fail_if_body_not_matches_regexp": GOLDEN_COMPLETION,
            },
        ),
        (
            "nvidia-nccl",
            TRAINING_NVIDIA_LABELS,
            300,
            {
                "method": "GET",
                "timeout_seconds": 10,
                "valid_status_codes": [200],
                "fail_if_body_not_matches_regexp": '"ok": true',
            },
        ),
    ]
    for probe_id, labels, interval, module in nvidia_http:
        spec = _spec(probe_id)
        checks.append(
            _common_check(
                spec=spec,
                temporal_provider_id=temporal_provider_id,
                labels=labels,
                prober="http",
                targets=[_http_url(base, spec["path"])],
                interval_seconds=interval,
                module_config=module,
            )
        )

    amd_http = [
        (
            "amd-rocm",
            AMD_LABELS,
            60,
            {
                "method": "GET",
                "timeout_seconds": 5,
                "valid_status_codes": [200],
                "fail_if_body_not_matches_regexp": '"device_count": 8',
            },
        ),
        (
            "amd-inference-health",
            {**AMD_LABELS, "workload": "inference"},
            30,
            {
                "method": "GET",
                "timeout_seconds": 5,
                "valid_status_codes": [200],
                "fail_if_body_not_matches_regexp": '"ok": true',
            },
        ),
        (
            "amd-inference-golden",
            {**AMD_LABELS, "workload": "inference"},
            30,
            {
                "method": "POST",
                "timeout_seconds": 8,
                "max_duration_seconds": 2,
                "valid_status_codes": [200],
                "headers": {"Content-Type": "application/json"},
                "body": {
                    "model": "llama-70b-rocm",
                    "messages": [{"role": "user", "content": GOLDEN_PROMPT}],
                    "max_tokens": 8,
                },
                "fail_if_body_not_matches_regexp": GOLDEN_COMPLETION,
            },
        ),
        (
            "amd-rccl",
            TRAINING_AMD_LABELS,
            300,
            {
                "method": "GET",
                "timeout_seconds": 10,
                "valid_status_codes": [200],
                "fail_if_body_not_matches_regexp": '"ok": true',
            },
        ),
    ]
    for probe_id, labels, interval, module in amd_http:
        spec = _spec(probe_id)
        checks.append(
            _common_check(
                spec=spec,
                temporal_provider_id=temporal_provider_id,
                labels=labels,
                prober="http",
                targets=[_http_url(base, spec["path"])],
                interval_seconds=interval,
                module_config=module,
            )
        )

    shared = [
        (
            "training-submit",
            {**TRAINING_NVIDIA_LABELS, "workload": "training"},
            180,
            {
                "method": "POST",
                "timeout_seconds": 10,
                "valid_status_codes": [200],
                "headers": {"Content-Type": "application/json"},
                "body": {"gpus": 1, "image": "ai-dc/cuda-canary:latest", "queue": "canary"},
                "fail_if_body_not_matches_regexp": '"state": "Running"',
            },
        ),
        (
            "training-checkpoint",
            {**TRAINING_NVIDIA_LABELS, "workload": "training"},
            180,
            {
                "method": "POST",
                "timeout_seconds": 10,
                "valid_status_codes": [200],
                "headers": {"Content-Type": "application/json"},
                "body": {"bytes": 1073741824, "op": "write_read"},
                "fail_if_body_not_matches_regexp": '"ok": true',
            },
        ),
        (
            "storage-health",
            {**DEFAULT_LABELS, "service": "gpu-training", "workload": "storage"},
            60,
            {
                "method": "GET",
                "timeout_seconds": 5,
                "valid_status_codes": [200],
                "fail_if_body_not_matches_regexp": '"ok": true',
            },
        ),
        (
            "netbox-dcim",
            {**DEFAULT_LABELS, "service": "ai-dc-1", "workload": "dcim"},
            120,
            {
                "method": "GET",
                "timeout_seconds": 5,
                "valid_status_codes": [200],
                "fail_if_body_not_matches_regexp": '"ok": true',
            },
        ),
    ]
    for probe_id, labels, interval, module in shared:
        spec = _spec(probe_id)
        checks.append(
            _common_check(
                spec=spec,
                temporal_provider_id=temporal_provider_id,
                labels=labels,
                prober="http",
                targets=[_http_url(base, spec["path"])],
                interval_seconds=interval,
                module_config=module,
            )
        )

    return copy.deepcopy(checks)
