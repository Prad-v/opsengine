"use client";

import { useCallback } from "react";
import useSWR from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast, showSuccessToast } from "@/shared/ui";
import type { ApprovalPolicy, ApprovalPolicyInput } from "./types";

export const approvalPolicyKeys = {
  all: "approval-policies",
  list: () => approvalPolicyKeys.all,
};

export function useApprovalPolicies() {
  const api = useApi();
  const {
    data: policies = [],
    error,
    isLoading,
    mutate,
  } = useSWR<ApprovalPolicy[]>(
    api.isReady() ? approvalPolicyKeys.list() : null,
    () => api.get("/approvals/policies"),
    { revalidateOnFocus: false }
  );

  const createPolicy = useCallback(
    async (body: ApprovalPolicyInput) => {
      try {
        const created = await api.post<ApprovalPolicy>(
          "/approvals/policies",
          body
        );
        await mutate();
        showSuccessToast("Approval policy created");
        return created;
      } catch (error) {
        showErrorToast(error, "Failed to create approval policy");
        throw error;
      }
    },
    [api, mutate]
  );

  const updatePolicy = useCallback(
    async (id: number, body: ApprovalPolicyInput) => {
      try {
        const updated = await api.put<ApprovalPolicy>(
          `/approvals/policies/${id}`,
          body
        );
        await mutate();
        showSuccessToast("Approval policy updated");
        return updated;
      } catch (error) {
        showErrorToast(error, "Failed to update approval policy");
        throw error;
      }
    },
    [api, mutate]
  );

  const deletePolicy = useCallback(
    async (id: number) => {
      try {
        await api.delete(`/approvals/policies/${id}`);
        await mutate();
        showSuccessToast("Approval policy deleted");
      } catch (error) {
        showErrorToast(error, "Failed to delete approval policy");
        throw error;
      }
    },
    [api, mutate]
  );

  return {
    policies,
    error,
    isLoading,
    mutate,
    createPolicy,
    updatePolicy,
    deletePolicy,
  };
}
