"use client";

import { useCallback } from "react";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast, showSuccessToast } from "@/shared/ui";
import type { ApprovalRequest } from "./types";
import { approvalKeys } from "./useApprovals";
import { useSWRConfig } from "swr";

export function useApprovalActions() {
  const api = useApi();
  const { mutate } = useSWRConfig();

  const revalidate = useCallback(async () => {
    await mutate(
      (key) => typeof key === "string" && key.startsWith(approvalKeys.all),
      undefined,
      { revalidate: true }
    );
  }, [mutate]);

  const approve = useCallback(
    async (id: number, comment?: string) => {
      try {
        const result = await api.post<ApprovalRequest>(
          `/approvals/${id}/approve`,
          comment ? { comment } : {}
        );
        await revalidate();
        showSuccessToast("Request approved");
        return result;
      } catch (error) {
        showErrorToast(error, "Failed to approve request");
        throw error;
      }
    },
    [api, revalidate]
  );

  const reject = useCallback(
    async (id: number, comment?: string) => {
      try {
        const result = await api.post<ApprovalRequest>(
          `/approvals/${id}/reject`,
          comment ? { comment } : {}
        );
        await revalidate();
        showSuccessToast("Request rejected");
        return result;
      } catch (error) {
        showErrorToast(error, "Failed to reject request");
        throw error;
      }
    },
    [api, revalidate]
  );

  const cancel = useCallback(
    async (id: number) => {
      try {
        const result = await api.post<ApprovalRequest>(
          `/approvals/${id}/cancel`
        );
        await revalidate();
        showSuccessToast("Request cancelled");
        return result;
      } catch (error) {
        showErrorToast(error, "Failed to cancel request");
        throw error;
      }
    },
    [api, revalidate]
  );

  return { approve, reject, cancel, revalidate };
}
