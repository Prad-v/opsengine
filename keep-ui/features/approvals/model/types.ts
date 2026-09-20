export const APPROVAL_ACTION_TYPES = [
  "create_maintenance",
  "node_maintenance",
  "run_workflow",
  "delete_resource",
  "temporal_signal",
  "webhook",
  "custom",
] as const;

export type ApprovalActionType = (typeof APPROVAL_ACTION_TYPES)[number];

export type ApprovalStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "expired"
  | "cancelled";

export type ApprovalRequest = {
  id: number;
  policy_id?: number | null;
  action_type: ApprovalActionType | string;
  status: ApprovalStatus | string;
  title: string;
  summary?: string | null;
  resource_type?: string | null;
  resource_id?: string | null;
  payload?: Record<string, unknown>;
  context?: Record<string, unknown>;
  callback?: Record<string, unknown>;
  result?: Record<string, unknown>;
  idempotency_key?: string | null;
  requested_by: string;
  requested_at: string;
  decided_by?: string | null;
  decided_at?: string | null;
  decision_comment?: string | null;
  expires_at?: string | null;
};

export type ApprovalPendingResponse = {
  status: "pending";
  request_id: number;
  approval: ApprovalRequest;
};

export type ApprovalPolicy = {
  id: number;
  name: string;
  action_type: ApprovalActionType | string;
  resource_type?: string | null;
  cel?: string | null;
  enabled: boolean;
  approver_roles: string[];
  approver_emails: string[];
  allow_self_approve: boolean;
  timeout_seconds?: number | null;
  priority: number;
  min_approvals: number;
  created_by?: string | null;
  created_at?: string;
  updated_by?: string | null;
  updated_at?: string;
};

export type ApprovalPolicyInput = {
  name: string;
  action_type: ApprovalActionType | string;
  resource_type?: string;
  cel?: string;
  enabled: boolean;
  approver_roles: string[];
  approver_emails: string[];
  allow_self_approve: boolean;
  timeout_seconds?: number;
  priority: number;
  min_approvals: number;
};

export function isApprovalPending(
  body: unknown
): body is ApprovalPendingResponse {
  if (!body || typeof body !== "object") {
    return false;
  }
  const value = body as Record<string, unknown>;
  return value.status === "pending" && typeof value.request_id === "number";
}
