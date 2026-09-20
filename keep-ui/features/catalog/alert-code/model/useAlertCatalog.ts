"use client";

import { useCallback } from "react";
import useSWR from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";
import type {
  AlertCatalogEntry,
  AlertCatalogEntryInput,
  EnhanceAlertCatalogDescriptionInput,
  EnhanceAlertCatalogDescriptionResult,
} from "./types";

export const alertCatalogKeys = {
  all: "alert-catalog",
  list: () => alertCatalogKeys.all,
  detail: (id: number) => `${alertCatalogKeys.all}::${id}`,
};

export function useAlertCatalog() {
  const api = useApi();

  const {
    data: catalog = [],
    error,
    isLoading,
    mutate,
  } = useSWR<AlertCatalogEntry[]>(
    api.isReady() ? alertCatalogKeys.list() : null,
    () => api.get("/alert-catalog"),
    { revalidateOnFocus: false }
  );

  const createEntry = useCallback(
    async (body: AlertCatalogEntryInput) => {
      const created = await api.post<AlertCatalogEntry>("/alert-catalog", body);
      await mutate();
      return created;
    },
    [api, mutate]
  );

  const updateEntry = useCallback(
    async (id: number, body: AlertCatalogEntryInput) => {
      const updated = await api.put<AlertCatalogEntry>(
        `/alert-catalog/${id}`,
        body
      );
      await mutate();
      return updated;
    },
    [api, mutate]
  );

  const deleteEntry = useCallback(
    async (id: number) => {
      const result = await api.delete(`/alert-catalog/${id}`);
      await mutate();
      return result;
    },
    [api, mutate]
  );

  const enhanceDescription = useCallback(
    async (body: EnhanceAlertCatalogDescriptionInput) => {
      return api.post<EnhanceAlertCatalogDescriptionResult>(
        "/alert-catalog/enhance-description",
        body
      );
    },
    [api]
  );

  return {
    catalog,
    error,
    isLoading,
    mutate,
    createEntry,
    updateEntry,
    deleteEntry,
    enhanceDescription,
  };
}
