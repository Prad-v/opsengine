"use client";

import { useCallback, useMemo } from "react";
import useSWR from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";
import { useWebsocket } from "@/utils/hooks/usePusher";
import type { ApprovalRequest, ApprovalStatus } from "./types";

export const approvalKeys = {
  all: "approvals",
  list: (status?: string, actionType?: string) =>
    [approvalKeys.all, "list", status, actionType].filter(Boolean).join("::"),
};

export function useApprovals(filters: {
  status?: ApprovalStatus | string;
  actionType?: string;
  resourceType?: string;
} = {}) {
  const api = useApi();
  const { bind, unbind } = useWebsocket();

  const key = api.isReady()
    ? approvalKeys.list(filters.status, filters.actionType)
    : null;

  const query = useMemo(() => {
    const params = new URLSearchParams();
    if (filters.status) {
      params.set("status", filters.status);
    }
    if (filters.actionType) {
      params.set("action_type", filters.actionType);
    }
    if (filters.resourceType) {
      params.set("resource_type", filters.resourceType);
    }
    const qs = params.toString();
    return qs ? `/approvals?${qs}` : "/approvals";
  }, [filters.status, filters.actionType, filters.resourceType]);

  const { data, error, isLoading, mutate } = useSWR<ApprovalRequest[]>(
    key,
    () => api.get(query),
    { revalidateOnFocus: false }
  );

  const refreshOnEvent = useCallback(() => {
    mutate();
  }, [mutate]);

  const subscribe = useCallback(() => {
    bind("approval-update", refreshOnEvent);
  }, [bind, refreshOnEvent]);

  const unsubscribe = useCallback(() => {
    unbind("approval-update", refreshOnEvent);
  }, [unbind, refreshOnEvent]);

  return {
    requests: data ?? [],
    error,
    isLoading,
    mutate,
    subscribe,
    unsubscribe,
  };
}
