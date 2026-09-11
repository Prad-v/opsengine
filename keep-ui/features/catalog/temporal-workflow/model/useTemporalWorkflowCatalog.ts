"use client";

import { useCallback } from "react";
import useSWR from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";
import { useIncidentActions } from "@/entities/incidents/model";
import type { IncidentDto } from "@/entities/incidents/model";
import type {
  TemporalCatalogEntry,
  TemporalCatalogEntryInput,
  TemporalCatalogStartResult,
} from "./types";

export const temporalWorkflowCatalogKeys = {
  all: "temporal-workflows",
  list: () => temporalWorkflowCatalogKeys.all,
  detail: (id: number) => `${temporalWorkflowCatalogKeys.all}::${id}`,
};

export function useTemporalWorkflowCatalog() {
  const api = useApi();

  const {
    data: catalog = [],
    error,
    isLoading,
    mutate,
  } = useSWR<TemporalCatalogEntry[]>(
    api.isReady() ? temporalWorkflowCatalogKeys.list() : null,
    () => api.get("/temporal-workflows"),
    { revalidateOnFocus: false }
  );

  const createEntry = useCallback(
    async (body: TemporalCatalogEntryInput) => {
      const created = await api.post<TemporalCatalogEntry>(
        "/temporal-workflows",
        body
      );
      await mutate();
      return created;
    },
    [api, mutate]
  );

  const updateEntry = useCallback(
    async (id: number, body: TemporalCatalogEntryInput) => {
      const updated = await api.put<TemporalCatalogEntry>(
        `/temporal-workflows/${id}`,
        body
      );
      await mutate();
      return updated;
    },
    [api, mutate]
  );

  const deleteEntry = useCallback(
    async (id: number) => {
      await api.delete(`/temporal-workflows/${id}`);
      await mutate();
    },
    [api, mutate]
  );

  return {
    catalog,
    error,
    isLoading,
    mutate,
    createEntry,
    updateEntry,
    deleteEntry,
  };
}

export function useStartTemporalCatalogWorkflow(incident: IncidentDto) {
  const api = useApi();
  const { mutateIncident } = useIncidentActions();

  const startCatalogWorkflow = useCallback(
    async (entry: TemporalCatalogEntry) => {
      const result = await api.post<TemporalCatalogStartResult>(
        `/temporal-workflows/${entry.id}/start`,
        { incident_id: incident.id }
      );
      mutateIncident(incident.id);
      return result;
    },
    [api, incident.id, mutateIncident]
  );

  return { startCatalogWorkflow };
}
