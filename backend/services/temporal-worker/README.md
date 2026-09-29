# Temporal worker for Keep ops demos on keep-ops.
#
# Workflows:
#   ListAndZipDirectory  — ls + zip under /data
#   RemediateNvidiaGpu   — cordon (L2+) → approve (L3+) → dcgmi diag →
#                          reset/uncordon (Pass) or email/isolate (Fail)
#                          Demo suite=2: cordon yes, approval no
#
# Local (via repo root):
#   docker compose -f docker-compose.temporal.yml up -d --build
#   # or: make deps-up / make start
#
# Register in Keep catalog (API must be up, Temporal provider installed):
#   python scripts/register_temporal_list_and_zip_catalog.py
#   python scripts/register_temporal_nvidia_gpu_catalog.py
#
# GPU e2e:
#   make demo-nvidia-gpu
#   Mock UI → GPU: rule + temp/mem  (or Force fail for diag ISOLATE / email path)
#   Keep → Service Topology (region / datacenter / row / rack / GPU)
#
# Real dcgmi (optional):
#   DCGM_DIAG_MODE=real DCGM_DIAG_REQUIRE_REAL=0  # fall back to mock if no binary

## Workflow

**Type:** `ListAndZipDirectory`  
**Task queue:** `keep-ops`

1. Activity `run_ls` — `ls -la` on a path under `TEMPORAL_WORKER_ROOT` (default `/data`)
2. Activity `create_zip_from_ls` — write stdout into `/data/output/ls-output-*.zip`

**Type:** `RemediateNvidiaGpu`

1. Approval when suite L3+ or `wait_for_approval: true`
2. `cordon_nvidia_gpu` when suite L2+
3. `run_dcgm_diag` — mock HTTP or real `dcgmi diag --json`
4. Fail/ISOLATE → email (leave cordoned)
5. Pass/RESET → remediate → uncordon → resolve

## Environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `TEMPORAL_ADDRESS` | `temporal:7233` | Temporal frontend |
| `TEMPORAL_NAMESPACE` | `default` | Namespace |
| `TEMPORAL_TASK_QUEUE` | `keep-ops` | Worker queue |
| `TEMPORAL_WORKER_ROOT` | `/data` | Sandboxed filesystem root |
| `KEEP_API_URL` | `http://host.docker.internal:8080` | Keep API for `request_keep_approval` |
| `KEEP_API_KEY` | `keepappkey` | API key used to POST `/approvals` |
| `GPU_MOCK_URL` | `http://host.docker.internal:8099` | Provider-mock GPU diag + remediate |
| `DCGM_DIAG_MODE` | `mock` | `mock` or `real` |
| `DCGM_DIAG_REQUIRE_REAL` | unset | Fail instead of mock fallback when set |
| `DCGM_DIAG_TIMEOUT_SEC` | `600` | Real CLI timeout |
| `DCGM_BIN` | PATH `dcgmi` | Optional binary path |

## Catalog registration

```bash
KEEP_API_URL=http://localhost:8080 KEEP_API_KEY=keepappkey \
  python scripts/register_temporal_list_and_zip_catalog.py
```

Or use **Catalog → Temporal workflow → Register** with:

- Name: `List and Zip Directory`
- Workflow type: `ListAndZipDirectory`
- Task queue: `keep-ops`
- Provider: your Temporal provider
- Input mapping: `{"incident_id":"id","path":"enrichments.list_path"}`
