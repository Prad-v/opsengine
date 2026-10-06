"""DCGM / NVIDIA GPU reserved alert codes for Keep catalog + provider-mock setup.

Grounded in dcgm-exporter ``etc/default-counters.csv`` help text, exporter-owned
collectors (XID / clock events / GPU health / P2P), and DCGM diagnostics docs:

  https://docs.nvidia.com/datacenter/dcgm/latest/reference/dcgm-exporter-metrics.html
  https://docs.nvidia.com/datacenter/dcgm/latest/reference/field-identifiers.html
  https://docs.nvidia.com/datacenter/dcgm/latest/reference/diagnostics/plugins/index.html
  https://docs.nvidia.com/datacenter/dcgm/latest/reference/diagnostics/errors.html

Detection notes in descriptions are recommended PromQL / ops policy — the exporter
emits metrics only; alerting is configured in VictoriaMetrics / Grafana / Keep.
"""

from __future__ import annotations

DCGM_DOCS_URL = (
    "https://docs.nvidia.com/datacenter/dcgm/latest/reference/"
    "dcgm-exporter-metrics.html"
)
DCGM_DIAG_DOCS_URL = (
    "https://docs.nvidia.com/datacenter/dcgm/latest/reference/diagnostics/"
    "plugins/index.html"
)
DCGM_DIAG_ERRORS_URL = (
    "https://docs.nvidia.com/datacenter/dcgm/latest/reference/diagnostics/"
    "errors.html"
)
XID_DOCS_URL = "https://docs.nvidia.com/deploy/xid-errors/"

# Codes that the VictoriaMetrics GPU remediate demo fires and may auto-run.
DEMO_AUTO_RUN_CODES = frozenset(
    {
        "DCGM_FI_DEV_GPU_TEMP",
        "DCGM_FI_DEV_FB_USED",
        "DCGM_FI_DEV_XID_ERRORS",
        "DCGM_FI_DEV_ECC_DBE_VOL_TOTAL",
        "DCGM_FI_DEV_THERMAL_VIOLATION",
        "DCGM_FI_DEV_NVLINK_CRC_FLIT_ERROR_COUNT_TOTAL",
        "DCGM_FI_DEV_NVLINK_CRC_FLIT_ERROR_TOTAL",
        "DCGM_FI_DEV_POWER_USAGE",
        "DCGM_EXP_GPU_HEALTH_STATUS",
    }
)


def _entry(
    code: str,
    name: str,
    description: str,
    *extra_tags: str,
    bucket: str = "exporter-default",
    runbook_url: str | None = None,
) -> dict:
    tags = ["nvidia", "dcgm", bucket, *extra_tags]
    # Preserve order, drop dupes.
    seen: set[str] = set()
    ordered: list[str] = []
    for tag in tags:
        tag = tag.strip().lower()
        if tag and tag not in seen:
            seen.add(tag)
            ordered.append(tag)
    return {
        "code": code,
        "name": name,
        "description": description,
        "runbook_url": runbook_url or DCGM_DOCS_URL,
        "tags": ordered,
        "disabled": False,
    }


# Shipped default + optional + exporter-owned metrics from DCGM Exporter.
# Label-only identity fields are included so the catalog can map them if rules
# ever fire; they are tagged ``label``.
CODES: tuple[dict, ...] = (
    # --- Shipped default metrics ---
    _entry(
        "DCGM_FI_DEV_SM_CLOCK",
        "DCGM SM clock",
        "Gauge: SM clock frequency in MHz. Unexpected drops often correlate with "
        "thermal/power throttle (clock-event / violation counters).",
        "clock",
        "util",
    ),
    _entry(
        "DCGM_FI_DEV_MEM_CLOCK",
        "DCGM memory clock",
        "Gauge: memory clock frequency in MHz. Sustained low clocks with load "
        "suggest power, thermal, or reliability throttling.",
        "clock",
        "memory",
    ),
    _entry(
        "DCGM_FI_DEV_MEMORY_TEMP",
        "DCGM memory temperature",
        "Gauge: GPU memory temperature in Celsius. Alert when approaching HBM "
        "thermal limits for the SKU; pair with GPU temp and thermal violation ns.",
        "thermal",
        "memory",
    ),
    _entry(
        "DCGM_FI_DEV_GPU_TEMP",
        "DCGM GPU temperature",
        "Gauge: GPU temperature in Celsius (dcgm-exporter default). Detect when "
        "sustained above site policy (demo: >85°C). Impact: thermal throttle, "
        "reduced throughput; check cooling/airflow and DCGM_FI_DEV_THERMAL_VIOLATION / "
        "DCGM_EXP_CLOCK_EVENTS_*.",
        "thermal",
    ),
    _entry(
        "DCGM_FI_DEV_POWER_USAGE",
        "DCGM board power",
        "Gauge: board power draw in watts. Detect when sustained near "
        "DCGM_FI_DEV_POWER_MGMT_LIMIT or DCGM_FI_DEV_ENFORCED_POWER_LIMIT "
        "(enable those optional fields). Impact: clocks may throttle under "
        "power cap; verify workload and rack PDU headroom.",
        "power",
    ),
    _entry(
        "DCGM_FI_DEV_POWER_MGMT_LIMIT",
        "DCGM power management limit",
        "Gauge: configured power management limit in watts (optional in "
        "default-counters.csv). Use as denominator for power-headroom alerts "
        "against DCGM_FI_DEV_POWER_USAGE.",
        "power",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_ENFORCED_POWER_LIMIT",
        "DCGM enforced power limit",
        "Gauge: effective power limit enforced by the driver after all limiters "
        "(optional). Prefer this over the configured limit when detecting "
        "power-cap throttling.",
        "power",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_TOTAL_ENERGY_CONSUMPTION",
        "DCGM total energy",
        "Counter: total energy consumption since the driver was last reloaded, "
        "in millijoules (mJ). Use increase()/rate for energy accounting — not "
        "a direct fault signal.",
        "power",
    ),
    _entry(
        "DCGM_FI_PROF_PCIE_TX_BYTES",
        "DCGM PCIe TX bytes",
        "Gauge (profiling): PCIe transmit rate including headers and payload, "
        "in bytes/s. Drop alongside rising PCIe replay suggests link issues.",
        "pcie",
        "profiling",
    ),
    _entry(
        "DCGM_FI_PROF_PCIE_RX_BYTES",
        "DCGM PCIe RX bytes",
        "Gauge (profiling): PCIe receive rate including headers and payload, "
        "in bytes/s.",
        "pcie",
        "profiling",
    ),
    _entry(
        "DCGM_FI_DEV_PCIE_REPLAY_COUNTER",
        "DCGM PCIe replay total",
        "Counter: total PCIe retries. Detect with increase()>0 over a window; "
        "rising rates indicate link/signal problems and map to "
        "DCGM_FR_PCI_REPLAY_RATE / PCIE_REPLAY_* findings.",
        "pcie",
        "error",
    ),
    _entry(
        "DCGM_FI_DEV_GPU_UTIL",
        "DCGM GPU utilization",
        "Gauge: GPU utilization in percent (sample period varies by product). "
        "Low util with high queue depth is a capacity/scheduling signal, not "
        "hardware fault.",
        "util",
    ),
    _entry(
        "DCGM_FI_DEV_MEM_COPY_UTIL",
        "DCGM memory copy utilization",
        "Gauge: memory copy engine utilization in percent.",
        "memory",
        "util",
    ),
    _entry(
        "DCGM_FI_DEV_ENC_UTIL",
        "DCGM encoder utilization",
        "Gauge: video encoder utilization in percent.",
        "util",
    ),
    _entry(
        "DCGM_FI_DEV_DEC_UTIL",
        "DCGM decoder utilization",
        "Gauge: video decoder utilization in percent.",
        "util",
    ),
    _entry(
        "DCGM_FI_DEV_XID_ERRORS",
        "DCGM XID error",
        "Gauge: value of the last NVIDIA XID error encountered (0 = none). "
        "Detect when != 0; prefer DCGM_EXP_XID_ERRORS_COUNT/TOTAL with xid label "
        "for rate/windowing (this field is sticky last-code). Map codes via NVIDIA "
        "XID docs (e.g. 48 DBE, 74 NVLink, 79 fallen off bus, 94/95 ECC). "
        "Often drives health_watch=ALL FAIL.",
        "xid",
        "error",
        "health",
        runbook_url=XID_DOCS_URL,
    ),
    _entry(
        "DCGM_FI_DEV_FB_FREE",
        "DCGM framebuffer free",
        "Gauge: framebuffer memory free in MiB. Use with FB_USED for utilization "
        "ratio alerts.",
        "memory",
    ),
    _entry(
        "DCGM_FI_DEV_FB_USED",
        "DCGM framebuffer used",
        "Gauge: framebuffer memory used in MiB (not percent). Detect when "
        "used/(used+free) exceeds policy (demo mocks ~95% util). Impact: CUDA "
        "OOM / eviction risk on inference nodes; scale or shed workload.",
        "memory",
    ),
    _entry(
        "DCGM_FI_DEV_FB_RESERVED",
        "DCGM framebuffer reserved",
        "Gauge: framebuffer memory reserved in MiB.",
        "memory",
    ),
    _entry(
        "DCGM_FI_DEV_NVLINK_BANDWIDTH_TOTAL",
        "DCGM NVLink throughput total",
        "Gauge: aggregate NVLink throughput across all lanes in MB/s.",
        "nvlink",
    ),
    _entry(
        "DCGM_FI_DEV_VGPU_LICENSE_STATUS",
        "DCGM vGPU license status",
        "Gauge: vGPU license status for the device. Non-licensed states block "
        "or degrade vGPU workloads.",
        "vgpu",
        "health",
    ),
    _entry(
        "DCGM_FI_DEV_UNCORRECTABLE_REMAPPED_ROWS",
        "DCGM uncorrectable remapped rows",
        "Counter: remapped rows for uncorrectable errors. Any sustained increase "
        "warrants quarantine planning; pair with row-remap failure and ECC DBE.",
        "ecc",
        "memory",
        "error",
    ),
    _entry(
        "DCGM_FI_DEV_CORRECTABLE_REMAPPED_ROWS",
        "DCGM correctable remapped rows",
        "Counter: remapped rows for correctable errors. Monitor growth rate; "
        "escalate if approaching device remap limits.",
        "ecc",
        "memory",
    ),
    _entry(
        "DCGM_FI_DEV_ROW_REMAP_FAILURE",
        "DCGM row remap failure",
        "Gauge: whether remapping of rows has failed (non-zero = failed). "
        "Treat as hardware fault — RESET/ISOLATE per diag finding "
        "DCGM_FR_ROW_REMAP_FAILURE; do not keep scheduling work.",
        "ecc",
        "memory",
        "error",
        "health",
    ),
    _entry(
        "DCGM_FI_DRIVER_VERSION",
        "DCGM driver version",
        "Label-only identity field (Driver Version) attached to other metrics. "
        "Not an alert signal by itself.",
        "label",
        bucket="exporter-default",
    ),
    _entry(
        "DCGM_FI_PROF_GR_ENGINE_ACTIVE",
        "DCGM graphics engine util",
        "Profiling gauge: ratio of time the graphics engine is active (0–1).",
        "profiling",
        "util",
    ),
    _entry(
        "DCGM_FI_PROF_PIPE_TENSOR_ACTIVE",
        "DCGM tensor util",
        "Profiling gauge: ratio of cycles the tensor (HMMA) pipe is active.",
        "profiling",
        "util",
    ),
    _entry(
        "DCGM_FI_PROF_DRAM_ACTIVE",
        "DCGM DRAM util",
        "Profiling gauge: ratio of cycles the device memory interface is active "
        "sending or receiving data.",
        "profiling",
        "memory",
        "util",
    ),
    # --- Shipped optional metrics (commented in default-counters.csv) ---
    _entry(
        "DCGM_FI_DEV_POWER_VIOLATION",
        "DCGM power violation",
        "Counter (optional): throttling duration due to power constraints, in "
        "nanoseconds. Detect with increase()>0; requires enabling the field in "
        "collectors CSV.",
        "power",
        "violation",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_THERMAL_VIOLATION",
        "DCGM thermal violation",
        "Counter (optional): throttling duration due to thermal constraints, in "
        "nanoseconds — not a temperature reading. Detect with increase()>0 over "
        "a scrape window; enable in collectors CSV. Action: cooling/airflow, "
        "then re-check GPU/memory temp.",
        "thermal",
        "violation",
        "throttle",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_SYNC_BOOST_VIOLATION",
        "DCGM sync boost violation",
        "Counter (optional): throttling duration due to sync-boost constraints "
        "(ns). Detect with increase()>0; requires collectors enable.",
        "violation",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_BOARD_LIMIT_VIOLATION",
        "DCGM board limit violation",
        "Counter (optional): throttling duration due to board limit constraints "
        "(ns).",
        "power",
        "violation",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_LOW_UTIL_VIOLATION",
        "DCGM low util violation",
        "Counter (optional): throttling duration due to low utilization (ns).",
        "util",
        "violation",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_RELIABILITY_VIOLATION",
        "DCGM reliability violation",
        "Counter (optional): throttling duration due to reliability constraints "
        "(ns). Treat rising values as hardware stress — investigate with diag.",
        "health",
        "violation",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_ECC_SBE_VOL_TOTAL",
        "DCGM ECC SBE volatile total",
        "Counter (optional): total single-bit volatile ECC errors. Detect "
        "increase()>0; usually correctable but rising rates need monitoring.",
        "ecc",
        "memory",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_ECC_DBE_VOL_TOTAL",
        "DCGM ECC DBE volatile total",
        "Counter (optional): total double-bit volatile (uncorrectable) ECC "
        "errors. Detect any increase()>0 → quarantine / RMA path; correlates "
        "with XID 48/95 and DCGM_FR_VOLATILE_DBE_DETECTED. Enable in collectors "
        "CSV.",
        "ecc",
        "memory",
        "error",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_ECC_SBE_AGG_TOTAL",
        "DCGM ECC SBE aggregate total",
        "Counter (optional): aggregate single-bit persistent ECC errors.",
        "ecc",
        "memory",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_ECC_DBE_AGG_TOTAL",
        "DCGM ECC DBE aggregate total",
        "Counter (optional): aggregate double-bit persistent ECC errors. Any "
        "growth is a strong hardware-fault signal.",
        "ecc",
        "memory",
        "error",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_RETIRED_SBE",
        "DCGM retired pages SBE",
        "Counter (optional): pages retired due to single-bit errors.",
        "ecc",
        "memory",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_RETIRED_DBE",
        "DCGM retired pages DBE",
        "Counter (optional): pages retired due to double-bit errors.",
        "ecc",
        "memory",
        "error",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_RETIRED_PENDING",
        "DCGM retired pages pending",
        "Gauge (optional): 1 if pages are pending retirement, else 0. Pending "
        "retirement typically needs GPU reset "
        "(DCGM_FR_PENDING_PAGE_RETIREMENTS).",
        "ecc",
        "memory",
        "requires-enable",
        bucket="exporter-optional",
    ),
    # Legacy COUNT_TOTAL NVLink names (still used by DCGM field IDs / demos).
    _entry(
        "DCGM_FI_DEV_NVLINK_CRC_FLIT_ERROR_COUNT_TOTAL",
        "DCGM NVLink CRC flit errors (legacy name)",
        "Counter: NVLink flow-control CRC errors (legacy field name with "
        "_COUNT_). Detect increase()>0; inspect fabric/cables. Current "
        "dcgm-exporter CSV also lists DCGM_FI_DEV_NVLINK_CRC_FLIT_ERROR_TOTAL "
        "— keep both codes for rule compatibility. Requires collectors enable.",
        "nvlink",
        "error",
        "requires-enable",
        "legacy-name",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_NVLINK_CRC_DATA_ERROR_COUNT_TOTAL",
        "DCGM NVLink CRC data errors (legacy name)",
        "Counter: NVLink data CRC errors (legacy _COUNT_ name). Prefer "
        "DCGM_FI_DEV_NVLINK_CRC_DATA_ERROR_TOTAL when aligning to current "
        "exporter CSV. Detect increase()>0.",
        "nvlink",
        "error",
        "requires-enable",
        "legacy-name",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_NVLINK_REPLAY_ERROR_COUNT_TOTAL",
        "DCGM NVLink replay errors (legacy name)",
        "Counter: NVLink replay errors (legacy _COUNT_ name). Alias of "
        "DCGM_FI_DEV_NVLINK_REPLAY_ERROR_TOTAL in current exporter CSV.",
        "nvlink",
        "error",
        "requires-enable",
        "legacy-name",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_NVLINK_RECOVERY_ERROR_COUNT_TOTAL",
        "DCGM NVLink recovery errors (legacy name)",
        "Counter: NVLink recovery errors (legacy _COUNT_ name). Alias of "
        "DCGM_FI_DEV_NVLINK_RECOVERY_ERROR_TOTAL in current exporter CSV.",
        "nvlink",
        "error",
        "requires-enable",
        "legacy-name",
        bucket="exporter-optional",
    ),
    # Canonical names from current dcgm-exporter default-counters.csv.
    _entry(
        "DCGM_FI_DEV_NVLINK_CRC_FLIT_ERROR_TOTAL",
        "DCGM NVLink CRC flit errors",
        "Counter (optional, pre-Hopper): total NVLink flow-control CRC errors "
        "across all lanes. Detect increase()>0 → fabric triage; escalate to "
        "DCGM_FR_NVLINK_* findings. Enable in collectors CSV.",
        "nvlink",
        "error",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_NVLINK_CRC_DATA_ERROR_TOTAL",
        "DCGM NVLink CRC data errors",
        "Counter (optional, pre-Hopper): total NVLink data CRC errors across "
        "all lanes. Detect increase()>0.",
        "nvlink",
        "error",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_NVLINK_REPLAY_ERROR_TOTAL",
        "DCGM NVLink replay errors",
        "Counter (optional, pre-Hopper): total NVLink replay errors across all "
        "lanes.",
        "nvlink",
        "error",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_NVLINK_RECOVERY_ERROR_TOTAL",
        "DCGM NVLink recovery errors",
        "Counter (optional, pre-Hopper): total NVLink recovery errors across "
        "all lanes.",
        "nvlink",
        "error",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_NVLINK_CRC_ERROR_TOTAL",
        "DCGM NVLink data-link CRC errors (Hopper+)",
        "Counter (optional, Hopper+): total NVLink data-link CRC errors.",
        "nvlink",
        "error",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_NVLINK_RECOVERY_TOTAL",
        "DCGM NVLink data-link recovery (Hopper+)",
        "Counter (optional, Hopper+): total NVLink data-link recovery errors.",
        "nvlink",
        "error",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_NVLINK_REPLAY_TOTAL",
        "DCGM NVLink data-link replay (Hopper+)",
        "Counter (optional, Hopper+): total NVLink data-link replay errors.",
        "nvlink",
        "error",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_NVLINK_RECOVERY_SUCCESSFUL_TOTAL",
        "DCGM NVLink recovery successful (Blackwell+)",
        "Counter (optional, Blackwell+): successful NVLink recovery events "
        "across all links.",
        "nvlink",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_NVLINK_RECOVERY_FAILED_TOTAL",
        "DCGM NVLink recovery failed (Blackwell+)",
        "Counter (optional, Blackwell+): failed NVLink recovery events. Detect "
        "increase()>0 as fabric instability.",
        "nvlink",
        "error",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_NVLINK_RECOVERY_EVENT_TOTAL",
        "DCGM NVLink recovery events (Blackwell+)",
        "Counter (optional, Blackwell+): total NVLink recovery events across "
        "all links.",
        "nvlink",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_NVLINK_BANDWIDTH_L0",
        "DCGM NVLink throughput L0",
        "Gauge (optional): NVLink lane 0 throughput in MB/s.",
        "nvlink",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_FABRIC_HEALTH_SUMMARY",
        "DCGM fabric health summary",
        "Gauge (optional): overall health of the GPU fabric. Non-pass values "
        "indicate cluster-wide link/fabric issues — correlate with NVLink and "
        "P2P status metrics.",
        "nvlink",
        "fabric",
        "health",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_FABRIC_HEALTH_MASK",
        "DCGM fabric health mask",
        "Gauge (optional): GPU fabric health status bitmask for subsystem "
        "drill-down.",
        "nvlink",
        "fabric",
        "health",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_NVML_VERSION",
        "DCGM NVML version",
        "Label: NVML version (identity).",
        "label",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_BRAND",
        "DCGM GPU brand",
        "Label: device brand (identity).",
        "label",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_SERIAL",
        "DCGM board serial",
        "Label: device serial number (identity).",
        "label",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_OEM_INFOROM_VER",
        "DCGM InfoROM OEM version",
        "Label: OEM InfoROM version.",
        "label",
        "inforom",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_ECC_INFOROM_VER",
        "DCGM InfoROM ECC version",
        "Label: ECC InfoROM version.",
        "label",
        "inforom",
        "ecc",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_POWER_INFOROM_VER",
        "DCGM InfoROM power version",
        "Label: power-management InfoROM version.",
        "label",
        "inforom",
        "power",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_INFOROM_IMAGE_VER",
        "DCGM InfoROM image version",
        "Label: InfoROM image version.",
        "label",
        "inforom",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_DEV_VBIOS_VERSION",
        "DCGM VBIOS version",
        "Label: VBIOS version of the device.",
        "label",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_PROF_SM_ACTIVE",
        "DCGM SM util",
        "Profiling gauge (optional): ratio of cycles an SM has at least one "
        "warp assigned.",
        "profiling",
        "util",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_PROF_SM_OCCUPANCY",
        "DCGM SM occupancy",
        "Profiling gauge (optional): ratio of warps resident on an SM.",
        "profiling",
        "util",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_PROF_PIPE_FP64_ACTIVE",
        "DCGM FP64 util",
        "Profiling gauge (optional): ratio of cycles the FP64 pipes are active.",
        "profiling",
        "util",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_PROF_PIPE_FP32_ACTIVE",
        "DCGM FP32 util",
        "Profiling gauge (optional): ratio of cycles the FP32 pipes are active.",
        "profiling",
        "util",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_PROF_PIPE_FP16_ACTIVE",
        "DCGM FP16 util",
        "Profiling gauge (optional): ratio of cycles the FP16 pipes are active.",
        "profiling",
        "util",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_PROF_SM_CYCLES_ELAPSED_TOTAL",
        "DCGM SM cycles elapsed",
        "Profiling counter (optional): total elapsed SM cycles.",
        "profiling",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_PROF_SM_CYCLES_ACTIVE_TOTAL",
        "DCGM SM cycles active",
        "Profiling counter (optional): total SM cycles with active warps.",
        "profiling",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_PROF_MMA_CYCLES_ACTIVE_TOTAL",
        "DCGM MMA cycles active",
        "Profiling counter (optional): total MMA tensor cycles active.",
        "profiling",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_PROF_DMMA_CYCLES_ACTIVE_TOTAL",
        "DCGM DMMA cycles active",
        "Profiling counter (optional): total DMMA tensor cycles active.",
        "profiling",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_PROF_HMMA_CYCLES_ACTIVE_TOTAL",
        "DCGM HMMA cycles active",
        "Profiling counter (optional): total HMMA tensor cycles active.",
        "profiling",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_PROF_IMMA_CYCLES_ACTIVE_TOTAL",
        "DCGM IMMA cycles active",
        "Profiling counter (optional): total IMMA tensor cycles active.",
        "profiling",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_PROF_DFMA_CYCLES_ACTIVE_TOTAL",
        "DCGM DFMA cycles active",
        "Profiling counter (optional): total DFMA tensor cycles active.",
        "profiling",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_PROF_PCIE_TX_BYTES_TOTAL",
        "DCGM PCIe TX bytes total",
        "Profiling counter (optional): cumulative PCIe transmitted bytes.",
        "pcie",
        "profiling",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_PROF_PCIE_RX_BYTES_TOTAL",
        "DCGM PCIe RX bytes total",
        "Profiling counter (optional): cumulative PCIe received bytes.",
        "pcie",
        "profiling",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_PROF_INT_CYCLES_ACTIVE_TOTAL",
        "DCGM INT cycles active",
        "Profiling counter (optional): total integer pipe cycles active.",
        "profiling",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_PROF_FP64_CYCLES_ACTIVE_TOTAL",
        "DCGM FP64 cycles active",
        "Profiling counter (optional): total FP64 pipe cycles active.",
        "profiling",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_PROF_FP32_CYCLES_ACTIVE_TOTAL",
        "DCGM FP32 cycles active",
        "Profiling counter (optional): total FP32 pipe cycles active.",
        "profiling",
        "requires-enable",
        bucket="exporter-optional",
    ),
    _entry(
        "DCGM_FI_PROF_FP16_CYCLES_ACTIVE_TOTAL",
        "DCGM FP16 cycles active",
        "Profiling counter (optional): total FP16 pipe cycles active.",
        "profiling",
        "requires-enable",
        bucket="exporter-optional",
    ),
    # --- Exporter-owned metrics ---
    _entry(
        "DCGM_EXP_CLOCK_EVENTS_COUNT",
        "DCGM clock events count",
        "Exporter gauge (optional): clock-event reasons observed during the "
        "configured window (throttle / power / thermal). Detect count>0 for "
        "thermal or power reasons; enable DCGM_EXP_* in collectors CSV.",
        "throttle",
        "clock",
        "thermal",
        "power",
        "requires-enable",
        bucket="exporter-owned",
    ),
    _entry(
        "DCGM_EXP_CLOCK_EVENTS_TOTAL",
        "DCGM clock events total",
        "Exporter counter (optional): cumulative inactive→active transitions "
        "per clock_event reason since exporter start (edge-counted).",
        "throttle",
        "clock",
        "requires-enable",
        bucket="exporter-owned",
    ),
    _entry(
        "DCGM_EXP_XID_ERRORS_COUNT",
        "DCGM XID errors count",
        "Exporter gauge (optional): XID samples in the configured window, "
        "grouped by xid label. Prefer this over DCGM_FI_DEV_XID_ERRORS for "
        "alerting (windowed, not sticky last code).",
        "xid",
        "error",
        "health",
        "requires-enable",
        bucket="exporter-owned",
        runbook_url=XID_DOCS_URL,
    ),
    _entry(
        "DCGM_EXP_XID_ERRORS_TOTAL",
        "DCGM XID errors total",
        "Exporter counter (optional): cumulative nonzero XID observations "
        "grouped by xid since exporter start. Detect increase by xid; map "
        "codes via NVIDIA XID docs.",
        "xid",
        "error",
        "health",
        "requires-enable",
        bucket="exporter-owned",
        runbook_url=XID_DOCS_URL,
    ),
    _entry(
        "DCGM_EXP_GPU_HEALTH_STATUS",
        "DCGM GPU health status",
        "Exporter gauge (optional): DCGM health-watch result per GPU — "
        "0=PASS, 10=WARN, 20=FAIL. Labels: health_watch "
        "(PCIE/NVLINK/MEM/THERMAL/POWER/DRIVER/ALL/…), health_error_code "
        "(DCGM_FR_*), health_error_severity (ISOLATE/RESET/MONITOR/…), "
        "health_error_category. Detect ==20 (or >=10). Devastating XIDs "
        "(e.g. 79, 95) surface on health_watch=ALL. Requires collectors enable.",
        "health",
        "error",
        "requires-enable",
        bucket="exporter-owned",
    ),
    _entry(
        "DCGM_EXP_P2P_STATUS",
        "DCGM P2P status",
        "Exporter gauge (optional): GPU P2P / NVLink peer status matrix entry "
        "(gpu ↔ peer_gpu labels). Non-OK links break multi-GPU collectives.",
        "nvlink",
        "health",
        "requires-enable",
        bucket="exporter-owned",
    ),
    # --- Active diagnostics plugins (dcgmi diag) ---
    _entry(
        "DCGM_DIAG_SOFTWARE",
        "DCGM diag: software deployment",
        "Level-1 software/deployment checks (libraries, device access, "
        "conflicting processes). Failures are usually CONFIG, not RMA.",
        "diag",
        "suite-1",
        bucket="diag-plugin",
        runbook_url=DCGM_DIAG_DOCS_URL,
    ),
    _entry(
        "DCGM_DIAG_CONTEXT_CREATE",
        "DCGM diag: context create",
        "Verify CUDA context creation on the target GPU.",
        "diag",
        "cuda",
        bucket="diag-plugin",
        runbook_url=DCGM_DIAG_DOCS_URL,
    ),
    _entry(
        "DCGM_DIAG_MEMORY",
        "DCGM diag: GPU memory",
        "Framebuffer allocation, patterns, cache, and observed memory errors "
        "(suite 2). Faulty memory → ISOLATE.",
        "diag",
        "memory",
        "suite-2",
        bucket="diag-plugin",
        runbook_url=DCGM_DIAG_DOCS_URL,
    ),
    _entry(
        "DCGM_DIAG_PCIE",
        "DCGM diag: PCIe bandwidth",
        "PCIe / P2P bandwidth, latency, link state, and error counters "
        "(suite 2).",
        "diag",
        "pcie",
        "suite-2",
        bucket="diag-plugin",
        runbook_url=DCGM_DIAG_DOCS_URL,
    ),
    _entry(
        "DCGM_DIAG_DIAGNOSTIC",
        "DCGM diag: compute stress",
        "Sustained matrix operations exercising compute and framebuffer paths "
        "(suite 3).",
        "diag",
        "compute",
        "suite-3",
        bucket="diag-plugin",
        runbook_url=DCGM_DIAG_DOCS_URL,
    ),
    _entry(
        "DCGM_DIAG_MEMORY_BANDWIDTH",
        "DCGM diag: memory bandwidth",
        "Local framebuffer bandwidth vs device threshold (suite 3).",
        "diag",
        "memory",
        "suite-3",
        bucket="diag-plugin",
        runbook_url=DCGM_DIAG_DOCS_URL,
    ),
    _entry(
        "DCGM_DIAG_TARGETED_STRESS",
        "DCGM diag: targeted stress",
        "Controlled GEMM workload sustaining a requested compute rate "
        "(suite 3).",
        "diag",
        "compute",
        "suite-3",
        bucket="diag-plugin",
        runbook_url=DCGM_DIAG_DOCS_URL,
    ),
    _entry(
        "DCGM_DIAG_TARGETED_POWER",
        "DCGM diag: targeted power",
        "Drive GPU toward a requested power level and monitor conditions "
        "(suite 3).",
        "diag",
        "power",
        "suite-3",
        bucket="diag-plugin",
        runbook_url=DCGM_DIAG_DOCS_URL,
    ),
    _entry(
        "DCGM_DIAG_NVBANDWIDTH",
        "DCGM diag: NVBandwidth",
        "Validate GPU copy paths over NVLink and PCIe (suite 3).",
        "diag",
        "nvlink",
        "suite-3",
        bucket="diag-plugin",
        runbook_url=DCGM_DIAG_DOCS_URL,
    ),
    _entry(
        "DCGM_DIAG_MEMTEST",
        "DCGM diag: memtest",
        "Extended GPU memory address/bit/coupling/retention patterns (suite 4).",
        "diag",
        "memory",
        "suite-4",
        bucket="diag-plugin",
        runbook_url=DCGM_DIAG_DOCS_URL,
    ),
    _entry(
        "DCGM_DIAG_PULSE_TEST",
        "DCGM diag: pulse test",
        "Rapid power/current swings to expose board delivery instability "
        "(suite 4).",
        "diag",
        "power",
        "suite-4",
        bucket="diag-plugin",
        runbook_url=DCGM_DIAG_DOCS_URL,
    ),
    # --- Diagnostic / health finding codes (severity → Keep action) ---
    _entry(
        "DCGM_FR_FAULTY_MEMORY",
        "DCGM FR: faulty memory",
        "Diagnostic found faulty GPU memory. Severity ISOLATE — cordon, do not "
        "auto-reset; schedule RMA.",
        "diag",
        "isolate",
        "memory",
        bucket="diag-error",
        runbook_url=DCGM_DIAG_ERRORS_URL,
    ),
    _entry(
        "DCGM_FR_VOLATILE_DBE_DETECTED",
        "DCGM FR: volatile DBE",
        "Uncorrectable double-bit ECC during health/diag. Severity ISOLATE.",
        "diag",
        "isolate",
        "memory",
        "ecc",
        bucket="diag-error",
        runbook_url=DCGM_DIAG_ERRORS_URL,
    ),
    _entry(
        "DCGM_FR_VOLATILE_SBE_DETECTED",
        "DCGM FR: volatile SBE",
        "Volatile single-bit ECC detected. Severity typically MONITOR — watch "
        "rate and remaps.",
        "diag",
        "monitor",
        "memory",
        "ecc",
        bucket="diag-error",
        runbook_url=DCGM_DIAG_ERRORS_URL,
    ),
    _entry(
        "DCGM_FR_PCI_REPLAY_RATE",
        "DCGM FR: PCIe replay rate",
        "Excessive PCIe replay rate. Severity ISOLATE — check riser/slot/"
        "firmware.",
        "diag",
        "isolate",
        "pcie",
        bucket="diag-error",
        runbook_url=DCGM_DIAG_ERRORS_URL,
    ),
    _entry(
        "DCGM_FR_PCIE_REPLAY_VIOLATION",
        "DCGM FR: PCIe replay violation",
        "PCIe replay violation from health watch. Severity often ISOLATE/"
        "TRIAGE — correlate with DCGM_FI_DEV_PCIE_REPLAY_COUNTER.",
        "diag",
        "isolate",
        "pcie",
        bucket="diag-error",
        runbook_url=DCGM_DIAG_ERRORS_URL,
    ),
    _entry(
        "DCGM_FR_NVLINK_ERROR_THRESHOLD",
        "DCGM FR: NVLink error threshold",
        "NVLink error threshold exceeded. Severity ISOLATE.",
        "diag",
        "isolate",
        "nvlink",
        bucket="diag-error",
        runbook_url=DCGM_DIAG_ERRORS_URL,
    ),
    _entry(
        "DCGM_FR_NVLINK_CRC_ERROR_THRESHOLD",
        "DCGM FR: NVLink CRC error threshold",
        "NVLink CRC error threshold exceeded. Severity ISOLATE — inspect "
        "cables/backplane.",
        "diag",
        "isolate",
        "nvlink",
        bucket="diag-error",
        runbook_url=DCGM_DIAG_ERRORS_URL,
    ),
    _entry(
        "DCGM_FR_NVLINK_ERROR_CRITICAL",
        "DCGM FR: NVLink critical error",
        "Critical NVLink error. Severity ISOLATE.",
        "diag",
        "isolate",
        "nvlink",
        bucket="diag-error",
        runbook_url=DCGM_DIAG_ERRORS_URL,
    ),
    _entry(
        "DCGM_FR_NVLINK_DOWN",
        "DCGM FR: NVLink down",
        "NVLink reported down. Severity ISOLATE — multi-GPU jobs will fail.",
        "diag",
        "isolate",
        "nvlink",
        bucket="diag-error",
        runbook_url=DCGM_DIAG_ERRORS_URL,
    ),
    _entry(
        "DCGM_FR_PENDING_PAGE_RETIREMENTS",
        "DCGM FR: pending page retirements",
        "Pending page retirements require GPU reset. Severity RESET.",
        "diag",
        "reset",
        "memory",
        bucket="diag-error",
        runbook_url=DCGM_DIAG_ERRORS_URL,
    ),
    _entry(
        "DCGM_FR_RETIRED_PAGES_LIMIT",
        "DCGM FR: retired pages limit",
        "Retired page count hit device limit. Severity ISOLATE — RMA.",
        "diag",
        "isolate",
        "memory",
        "ecc",
        bucket="diag-error",
        runbook_url=DCGM_DIAG_ERRORS_URL,
    ),
    _entry(
        "DCGM_FR_RETIRED_PAGES_DBE_LIMIT",
        "DCGM FR: retired pages DBE limit",
        "DBE-driven retired pages at limit. Severity ISOLATE.",
        "diag",
        "isolate",
        "memory",
        "ecc",
        bucket="diag-error",
        runbook_url=DCGM_DIAG_ERRORS_URL,
    ),
    _entry(
        "DCGM_FR_ROW_REMAP_FAILURE",
        "DCGM FR: row remap failure",
        "Row remap failure; GPU reset required. Severity RESET (escalate to "
        "ISOLATE if reset does not clear).",
        "diag",
        "reset",
        "memory",
        bucket="diag-error",
        runbook_url=DCGM_DIAG_ERRORS_URL,
    ),
    _entry(
        "DCGM_FR_UNCONTAINED_ERROR",
        "DCGM FR: uncontained error",
        "Uncontained GPU error (often XID 95 class). Severity ISOLATE — drain "
        "node and do not auto-remediate.",
        "diag",
        "isolate",
        "health",
        "xid",
        bucket="diag-error",
        runbook_url=DCGM_DIAG_ERRORS_URL,
    ),
    _entry(
        "DCGM_FR_CONTAINED_ERROR",
        "DCGM FR: contained error",
        "Contained GPU error (often XID 94 class). Severity typically RESET/"
        "MONITOR per site policy.",
        "diag",
        "reset",
        "health",
        "xid",
        bucket="diag-error",
        runbook_url=DCGM_DIAG_ERRORS_URL,
    ),
    _entry(
        "DCGM_FR_FALLEN_OFF_BUS",
        "DCGM FR: fallen off bus",
        "GPU has fallen off the bus (XID 79). Severity ISOLATE — power cycle / "
        "hardware replace; surfaces on health_watch=ALL.",
        "diag",
        "isolate",
        "health",
        "xid",
        "pcie",
        bucket="diag-error",
        runbook_url=DCGM_DIAG_ERRORS_URL,
    ),
    _entry(
        "DCGM_FR_THERMAL_VIOLATIONS",
        "DCGM FR: thermal violations",
        "Thermal violations observed during diagnostics/health. Severity "
        "MONITOR — fix cooling before stressing the GPU again.",
        "diag",
        "monitor",
        "thermal",
        bucket="diag-error",
        runbook_url=DCGM_DIAG_ERRORS_URL,
    ),
    _entry(
        "DCGM_FR_CLOCK_THROTTLE_THERMAL",
        "DCGM FR: clock throttle thermal",
        "Clocks throttled due to thermal limits (health watch). Severity "
        "MONITOR.",
        "diag",
        "monitor",
        "thermal",
        "throttle",
        bucket="diag-error",
        runbook_url=DCGM_DIAG_ERRORS_URL,
    ),
    _entry(
        "DCGM_FR_CLOCK_THROTTLE_POWER",
        "DCGM FR: clock throttle power",
        "Clocks throttled due to power limits (health watch). Severity MONITOR.",
        "diag",
        "monitor",
        "power",
        "throttle",
        bucket="diag-error",
        runbook_url=DCGM_DIAG_ERRORS_URL,
    ),
    _entry(
        "DCGM_FR_TEMP_VIOLATION",
        "DCGM FR: temperature violation",
        "Temperature violation from health/diag. Severity MONITOR — verify "
        "cooling and DCGM_FI_DEV_GPU_TEMP.",
        "diag",
        "monitor",
        "thermal",
        bucket="diag-error",
        runbook_url=DCGM_DIAG_ERRORS_URL,
    ),
    _entry(
        "DCGM_FR_CORRUPT_INFOROM",
        "DCGM FR: corrupt InfoROM",
        "Corrupt InfoROM detected. Severity ISOLATE — firmware/RMA path.",
        "diag",
        "isolate",
        "inforom",
        bucket="diag-error",
        runbook_url=DCGM_DIAG_ERRORS_URL,
    ),
    _entry(
        "DCGM_FR_BAD_CUDA_ENV",
        "DCGM FR: bad CUDA environment",
        "CUDA environment/config problem. Severity CONFIG — fix software, not "
        "hardware.",
        "diag",
        "config",
        "cuda",
        bucket="diag-error",
        runbook_url=DCGM_DIAG_ERRORS_URL,
    ),
    _entry(
        "DCGM_FR_LOW_BANDWIDTH",
        "DCGM FR: low bandwidth",
        "PCIe/NVLink bandwidth below threshold. Severity TRIAGE.",
        "diag",
        "triage",
        "pcie",
        bucket="diag-error",
        runbook_url=DCGM_DIAG_ERRORS_URL,
    ),
    _entry(
        "DCGM_FR_HIGH_LATENCY",
        "DCGM FR: high latency",
        "PCIe/NVLink latency above threshold. Severity TRIAGE.",
        "diag",
        "triage",
        "pcie",
        bucket="diag-error",
        runbook_url=DCGM_DIAG_ERRORS_URL,
    ),
    _entry(
        "DCGM_FR_XID_ERROR",
        "DCGM FR: XID error",
        "XID observed during diagnostics/health. Severity TRIAGE — map the "
        "numeric XID before choosing RESET vs ISOLATE.",
        "diag",
        "triage",
        "xid",
        bucket="diag-error",
        runbook_url=DCGM_DIAG_ERRORS_URL,
    ),
    _entry(
        "DCGM_FR_SXID_ERROR",
        "DCGM FR: SXID error",
        "NVSwitch SXID error. Severity typically ISOLATE for fabric path.",
        "diag",
        "isolate",
        "nvlink",
        bucket="diag-error",
        runbook_url=DCGM_DIAG_ERRORS_URL,
    ),
    _entry(
        "DCGM_FR_DBE_VIOLATION",
        "DCGM FR: DBE violation",
        "Double-bit ECC violation from health watch. Severity ISOLATE.",
        "diag",
        "isolate",
        "ecc",
        "memory",
        bucket="diag-error",
        runbook_url=DCGM_DIAG_ERRORS_URL,
    ),
    _entry(
        "DCGM_FR_SBE_VIOLATION",
        "DCGM FR: SBE violation",
        "Single-bit ECC violation from health watch. Severity MONITOR/TRIAGE.",
        "diag",
        "monitor",
        "ecc",
        "memory",
        bucket="diag-error",
        runbook_url=DCGM_DIAG_ERRORS_URL,
    ),
    _entry(
        "DCGM_FR_GPU_RECOVERY_RESET",
        "DCGM FR: GPU recovery reset",
        "DCGM recommends GPU reset recovery. Severity RESET.",
        "diag",
        "reset",
        "health",
        bucket="diag-error",
        runbook_url=DCGM_DIAG_ERRORS_URL,
    ),
    _entry(
        "DCGM_FR_GPU_RECOVERY_REBOOT",
        "DCGM FR: GPU recovery reboot",
        "DCGM recommends node reboot recovery. Severity RESET (host-level).",
        "diag",
        "reset",
        "health",
        bucket="diag-error",
        runbook_url=DCGM_DIAG_ERRORS_URL,
    ),
    _entry(
        "DCGM_FR_GPU_RECOVERY_DRAIN_P2P",
        "DCGM FR: GPU recovery drain P2P",
        "DCGM recommends drain P2P traffic before recovery. Severity ISOLATE/"
        "RESET sequencing.",
        "diag",
        "isolate",
        "nvlink",
        bucket="diag-error",
        runbook_url=DCGM_DIAG_ERRORS_URL,
    ),
    _entry(
        "DCGM_FR_GPU_RECOVERY_DRAIN_RESET",
        "DCGM FR: GPU recovery drain reset",
        "DCGM recommends drain then reset. Severity RESET after cordon/drain.",
        "diag",
        "reset",
        "health",
        bucket="diag-error",
        runbook_url=DCGM_DIAG_ERRORS_URL,
    ),
)
