# Temporal worker for Keep ops demos on keep-ops.
#
# Workflows:
#   ListAndZipDirectory  — ls + zip under /data
#   RemediateNvidiaGpu   — remediate provider-mock GPU server; resolve or email
#                          wait_for_approval=false by default (GPU demo unchanged)
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
#   Mock UI → GPU: rule + temp/mem  (or Force fail for email path)
#   Keep → Service Topology (region / datacenter / row / rack / GPU)

## Workflow

**Type:** `ListAndZipDirectory`  
**Task queue:** `keep-ops`

1. Activity `run_ls` — `ls -la` on a path under `TEMPORAL_WORKER_ROOT` (default `/data`)
2. Activity `create_zip_from_ls` — write stdout into `/data/output/ls-output-*.zip`

## Environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `TEMPORAL_ADDRESS` | `temporal:7233` | Temporal frontend |
| `TEMPORAL_NAMESPACE` | `default` | Namespace |
| `TEMPORAL_TASK_QUEUE` | `keep-ops` | Worker queue |
| `TEMPORAL_WORKER_ROOT` | `/data` | Sandboxed filesystem root |
| `KEEP_API_URL` | `http://host.docker.internal:8080` | Keep API for `request_keep_approval` |
| `KEEP_API_KEY` | `keepappkey` | API key used to POST `/approvals` |

`RemediateNvidiaGpu` accepts `wait_for_approval`. Default is **false** so the GPU demo still remediates immediately. When true, the worker POSTs Keep `/approvals` and waits on signal `approve`.

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
