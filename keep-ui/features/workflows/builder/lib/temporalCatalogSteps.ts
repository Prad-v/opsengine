import type { Provider } from "@/shared/api/providers";
import type { V2ActionStep } from "@/entities/workflows/model/types";
import type { TemporalCatalogEntry } from "@/features/catalog/temporal-workflow";

/**
 * Map a catalog input_mapping path to a Keep mustache expression.
 * Catalog paths are incident-oriented (id, enrichments.foo, …).
 */
export function catalogPathToKeepTemplate(path: string): string {
  const cleaned = (path || "").trim();
  if (!cleaned) {
    return "";
  }
  if (cleaned.includes("{{")) {
    return cleaned;
  }
  if (cleaned.startsWith("incident.") || cleaned.startsWith("alert.")) {
    return `{{ ${cleaned} }}`;
  }
  return `{{ incident.${cleaned} }}`;
}

/**
 * Convert Temporal workflow_id_template (chevron) into Keep mustache,
 * baking the catalog key in place of {{catalog.id}}.
 */
export function catalogWorkflowIdToKeepTemplate(
  template: string | null | undefined,
  catalogKey: string
): string {
  const fallback = `incident-{{ incident.id }}-${catalogKey}`;
  if (!template || !template.trim()) {
    return fallback;
  }
  return template
    .replace(/\{\{\s*catalog\.id\s*\}\}/g, catalogKey)
    .replace(/\{\{\s*catalog\.name\s*\}\}/g, catalogKey)
    .replace(/\{\{\s*incident\.([^}\s]+)\s*\}\}/g, "{{ incident.$1 }}");
}

function buildArgFromInputMapping(
  inputMapping: Record<string, string> | null | undefined
): Record<string, string> {
  const arg: Record<string, string> = {};
  for (const [key, path] of Object.entries(inputMapping || {})) {
    arg[key] = catalogPathToKeepTemplate(path);
  }
  return arg;
}

/**
 * Build pre-filled Keep workflow builder action templates from Temporal catalog entries.
 * Uses type `action-temporal` so YAML serialization and Temporal provider stay unchanged.
 */
export function getTemporalCatalogActionTemplates(
  catalog: TemporalCatalogEntry[],
  providers: Provider[]
): Omit<V2ActionStep, "id">[] {
  const temporalProvider = providers.find((p) => p.type === "temporal");
  const actionParams =
    temporalProvider?.notify_params?.filter((p) => p !== "kwargs") ?? [
      "operation",
      "workflow_type",
      "task_queue",
      "workflow_id",
      "arg",
      "args",
      "signal_name",
      "signal_args",
      "reason",
      "run_id",
    ];

  return catalog
    .filter((entry) => !entry.disabled)
    .map((entry) => {
      const providerConfigName =
        entry.provider_name ||
        providers.find((p) => p.id === entry.provider_id)?.details?.name ||
        providers.find((p) => p.id === entry.provider_id)?.display_name ||
        "temporal";

      return {
        componentType: "task" as const,
        type: "action-temporal",
        name: entry.name,
        properties: {
          actionParams,
          config: providerConfigName,
          with: {
            operation: "start_workflow",
            workflow_type: entry.workflow_type,
            task_queue: entry.task_queue,
            workflow_id: catalogWorkflowIdToKeepTemplate(
              entry.workflow_id_template,
              entry.catalog_key
            ),
            arg: buildArgFromInputMapping(entry.input_mapping),
          },
        },
      };
    });
}
