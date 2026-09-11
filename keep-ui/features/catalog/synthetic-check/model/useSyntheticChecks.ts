"use client";

import { useCallback } from "react";
import useSWR from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";
import type {
  SyntheticCheck,
  SyntheticCheckInput,
  SyntheticCheckRunResult,
} from "./types";

export const syntheticCheckKeys = {
  all: "synthetic-checks",
  list: () => syntheticCheckKeys.all,
  detail: (id: number) => `${syntheticCheckKeys.all}::${id}`,
};

export function useSyntheticChecks() {
  const api = useApi();

  const {
    data: checks = [],
    error,
    isLoading,
    mutate,
  } = useSWR<SyntheticCheck[]>(
    api.isReady() ? syntheticCheckKeys.list() : null,
    () => api.get("/synthetic-checks"),
    { revalidateOnFocus: false }
  );

  const createCheck = useCallback(
    async (body: SyntheticCheckInput) => {
      const created = await api.post<SyntheticCheck>("/synthetic-checks", body);
      await mutate();
      return created;
    },
    [api, mutate]
  );

  const updateCheck = useCallback(
    async (id: number, body: SyntheticCheckInput) => {
      const updated = await api.put<SyntheticCheck>(
        `/synthetic-checks/${id}`,
        body
      );
      await mutate();
      return updated;
    },
    [api, mutate]
  );

  const deleteCheck = useCallback(
    async (id: number) => {
      await api.delete(`/synthetic-checks/${id}`);
      await mutate();
    },
    [api, mutate]
  );

  const runCheck = useCallback(
    async (id: number) => {
      const result = await api.post<SyntheticCheckRunResult>(
        `/synthetic-checks/${id}/run`,
        {}
      );
      await mutate();
      return result;
    },
    [api, mutate]
  );

  return {
    checks,
    error,
    isLoading,
    mutate,
    createCheck,
    updateCheck,
    deleteCheck,
    runCheck,
  };
}
