import { MaintenanceRule } from "@/app/(keep)/maintenance/model";
import type {
  MaintenancePreviewResult,
  MaintenanceRuleCreate,
} from "@/app/(keep)/maintenance/model";
import { isApprovalPending, type ApprovalPendingResponse } from "@/features/approvals";
import useSWR, { SWRConfiguration } from "swr";
import { useCallback } from "react";
import { toast } from "react-toastify";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast } from "@/shared/ui";

export const useMaintenanceRules = (
  options: SWRConfiguration = {
    revalidateOnFocus: false,
  }
) => {
  const api = useApi();

  const { data, isLoading, error, mutate } = useSWR<MaintenanceRule[]>(
    api.isReady() ? "/maintenance" : null,
    (url) => api.get(url),
    options
  );

  const createRule = useCallback(
    async (body: MaintenanceRuleCreate) => {
      const created = await api.post<
        MaintenanceRule | ApprovalPendingResponse
      >("/maintenance", body);
      await mutate();
      return created;
    },
    [api, mutate]
  );

  const updateRule = useCallback(
    async (id: number, body: MaintenanceRuleCreate) => {
      const updated = await api.put<MaintenanceRule>(
        `/maintenance/${id}`,
        body
      );
      await mutate();
      return updated;
    },
    [api, mutate]
  );

  const deleteRule = useCallback(
    async (id: number) => {
      const result = await api.delete(`/maintenance/${id}`);
      await mutate();
      return result;
    },
    [api, mutate]
  );

  const endNow = useCallback(
    async (id: number) => {
      const updated = await api.post<MaintenanceRule>(
        `/maintenance/${id}/end-now`
      );
      await mutate();
      return updated;
    },
    [api, mutate]
  );

  const extend = useCallback(
    async (id: number, durationSeconds = 1800) => {
      const updated = await api.post<MaintenanceRule>(
        `/maintenance/${id}/extend`,
        { duration_seconds: durationSeconds }
      );
      await mutate();
      return updated;
    },
    [api, mutate]
  );

  const preview = useCallback(
    async (celQuery: string) => {
      return api.post<MaintenancePreviewResult>("/maintenance/preview", {
        cel_query: celQuery,
      });
    },
    [api]
  );

  const deleteRuleWithToast = useCallback(
    async (id: number) => {
      try {
        const result = await deleteRule(id);
        if (isApprovalPending(result)) {
          toast.success("Delete submitted for approval");
          return result;
        }
        toast.success("Maintenance rule deleted successfully");
        return result;
      } catch (error) {
        showErrorToast(error, "Failed to delete maintenance rule");
        throw error;
      }
    },
    [deleteRule]
  );

  return {
    data,
    isLoading,
    error,
    mutate,
    createRule,
    updateRule,
    deleteRule,
    deleteRuleWithToast,
    endNow,
    extend,
    preview,
  };
};
