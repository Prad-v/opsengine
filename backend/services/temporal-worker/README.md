# Temporal worker for Keep ops demos (ListAndZipDirectory on keep-ops).
#
# Local (via repo root):
#   docker compose -f docker-compose.temporal.yml up -d --build
#   # or: make deps-up / make start
#
# Register in Keep catalog (API must be up, Temporal provider installed):
#   python scripts/register_temporal_list_and_zip_catalog.py
#
# Then: Incident → Workflows → Start for incident
# Optional incident enrichment: list_path=sample  (lists /data/sample in the worker)

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
