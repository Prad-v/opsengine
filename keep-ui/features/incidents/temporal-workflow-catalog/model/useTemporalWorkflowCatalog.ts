"use client";

import { useCallback, useMemo } from "react";
import useSWR from "swr";
import { useProviders } from "@/utils/hooks/useProviders";
import { useIncidentActions } from "@/entities/incidents/model";
import type { IncidentDto } from "@/entities/incidents/model";
import type { Provider } from "@/shared/api/providers";
import type {
  TemporalCatalogEntry,
  TemporalCatalogStartResult,
} from "./types";

function isTemporalProvider(provider: Provider): boolean {
  return provider.type === "temporal";
}

function parseCatalogJson(raw: unknown): Record<string, unknown>[] {
  if (!raw) {
    return [];
  }
  if (Array.isArray(raw)) {
    return raw.filter((item) => item && typeof item === "object") as Record<
      string,
      unknown
    >[];
  }
  if (typeof raw === "string") {
    const trimmed = raw.trim();
    if (!trimmed) {
      return [];
    }
    const parsed = JSON.parse(trimmed);
    if (!Array.isArray(parsed)) {
      throw new Error("workflow_catalog must be a JSON array");
    }
    return parsed;
  }
  throw new Error("workflow_catalog must be a JSON array or string");
}

function mapCatalogEntries(
  provider: Provider,
  list: Record<string, unknown>[]
): TemporalCatalogEntry[] {
  return list.map((item) => ({
    id: String(item.id),
    name: String(item.name ?? item.id),
    description: item.description ? String(item.description) : "",
    workflow_type: String(item.workflow_type),
    task_queue: String(item.task_queue),
    workflow_id_template: item.workflow_id_template
      ? String(item.workflow_id_template)
      : undefined,
    input_mapping: (item.input_mapping as Record<string, string>) ?? {},
    provider_id: provider.id,
    provider_name: provider.details?.name || provider.display_name,
  }));
}

function catalogFromProviderDetails(provider: Provider): TemporalCatalogEntry[] {
  const raw = provider.details?.authentication?.workflow_catalog;
  return mapCatalogEntries(provider, parseCatalogJson(raw));
}

function errorMessage(error: unknown): string {
  if (!error) {
    return "";
  }
  if (typeof error === "string") {
    return error;
  }
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === "object" && error !== null && "message" in error) {
    return String((error as { message: unknown }).message);
  }
  return String(error);
}

export function useTemporalWorkflowCatalog(incident: IncidentDto) {
  const { data: providersData, isLoading: isProvidersLoading } = useProviders();
  const { invokeProviderMethod, enrichIncident, mutateIncident } =
    useIncidentActions();

  const temporalProviders = useMemo(
    () =>
      (providersData?.installed_providers ?? []).filter(isTemporalProvider),
    [providersData?.installed_providers]
  );

  const catalogKey =
    temporalProviders.length > 0
      ? `temporal-catalog::${temporalProviders.map((p) => p.id).join(",")}`
      : null;

  const {
    data: catalog = [],
    error,
    isLoading: isCatalogLoading,
    mutate,
  } = useSWR<TemporalCatalogEntry[]>(
    catalogKey,
    async () => {
      const entries: TemporalCatalogEntry[] = [];
      const errors: string[] = [];

      for (const provider of temporalProviders) {
        try {
          const result = await invokeProviderMethod(
            provider.id,
            "get_workflow_catalog",
            {}
          );
          const list = Array.isArray(result) ? result : [];
          entries.push(...mapCatalogEntries(provider, list));
        } catch (invokeError) {
          const message = errorMessage(invokeError);
          // Fallback: read Keep-managed catalog JSON from provider config.
          // This covers stale API processes that do not yet expose the method.
          try {
            const fallback = catalogFromProviderDetails(provider);
            entries.push(...fallback);
            if (
              fallback.length === 0 &&
              /method not found/i.test(message)
            ) {
              errors.push(
                `${provider.details?.name || provider.display_name}: API method missing. Restart the Keep API (make stop && make start), then add workflow_catalog on the Temporal provider.`
              );
            } else if (fallback.length === 0 && message) {
              errors.push(
                `${provider.details?.name || provider.display_name}: ${message}`
              );
            }
          } catch (parseError) {
            errors.push(
              `${provider.details?.name || provider.display_name}: ${errorMessage(parseError) || message}`
            );
          }
        }
      }

      if (entries.length === 0 && errors.length > 0) {
        throw new Error(errors.join(" | "));
      }
      return entries;
    },
    { revalidateOnFocus: false }
  );

  const startCatalogWorkflow = useCallback(
    async (entry: TemporalCatalogEntry) => {
      const incidentPayload = {
        id: incident.id,
        name: incident.user_generated_name || incident.ai_generated_name,
        user_generated_name: incident.user_generated_name,
        ai_generated_name: incident.ai_generated_name,
        severity: incident.severity,
        status: incident.status,
        services: incident.services,
        alert_sources: incident.alert_sources,
        alerts_count: incident.alerts_count,
        enrichments: incident.enrichments ?? {},
      };

      const result = (await invokeProviderMethod(
        entry.provider_id,
        "start_workflow_from_catalog",
        {
          catalog_id: entry.id,
          incident: incidentPayload,
        }
      )) as TemporalCatalogStartResult;

      const previous =
        (incident.enrichments?.temporal_workflows as
          | TemporalCatalogStartResult[]
          | undefined) ?? [];
      const next = [
        ...previous.filter(
          (item) =>
            !(
              item.catalog_id === result.catalog_id &&
              item.workflow_id === result.workflow_id
            )
        ),
        {
          catalog_id: result.catalog_id,
          catalog_name: result.catalog_name ?? entry.name,
          workflow_id: result.workflow_id,
          run_id: result.run_id,
          workflow_type: result.workflow_type,
          task_queue: result.task_queue,
          namespace: result.namespace,
          started_at: new Date().toISOString(),
        },
      ];

      await enrichIncident(incident.id, {
        temporal_workflows: next,
        temporal_last_workflow_id: result.workflow_id,
        temporal_last_run_id: result.run_id,
        temporal_last_catalog_id: result.catalog_id,
      });
      mutateIncident(incident.id);

      return result;
    },
    [enrichIncident, incident, invokeProviderMethod, mutateIncident]
  );

  return {
    temporalProviders,
    catalog,
    error,
    isLoading: isProvidersLoading || (!!catalogKey && isCatalogLoading),
    mutate,
    startCatalogWorkflow,
  };
}
