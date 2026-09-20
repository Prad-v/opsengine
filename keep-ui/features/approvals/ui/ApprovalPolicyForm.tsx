"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  Button,
  Select,
  SelectItem,
  Text,
  TextInput,
} from "@tremor/react";
import {
  APPROVAL_ACTION_TYPES,
  type ApprovalActionType,
  type ApprovalPolicy,
  type ApprovalPolicyInput,
} from "../model/types";
import { formatApprovalCelQuery } from "../lib/approvalPolicyCel";
import {
  ApprovalPolicyCelFilter,
  useApprovalPolicyCelQuery,
} from "./ApprovalPolicyCelFilter";

interface ApprovalPolicyFormProps {
  initial?: ApprovalPolicy | null;
  onSubmit: (body: ApprovalPolicyInput) => Promise<void>;
  onCancel: () => void;
}

export function ApprovalPolicyForm({
  initial,
  onSubmit,
  onCancel,
}: ApprovalPolicyFormProps) {
  const [name, setName] = useState("");
  const [actionType, setActionType] =
    useState<ApprovalActionType>("create_maintenance");
  const [resourceType, setResourceType] = useState("");
  const [approverRoles, setApproverRoles] = useState("admin");
  const [approverEmails, setApproverEmails] = useState("");
  const [allowSelfApprove, setAllowSelfApprove] = useState(false);
  const [enabled, setEnabled] = useState(true);
  const [timeoutSeconds, setTimeoutSeconds] = useState("");
  const [priority, setPriority] = useState("0");
  const [isSaving, setIsSaving] = useState(false);
  const { query, setQuery } = useApprovalPolicyCelQuery(initial?.cel);

  useEffect(() => {
    if (initial) {
      setName(initial.name);
      setActionType((initial.action_type as ApprovalActionType) || "custom");
      setResourceType(initial.resource_type || "");
      setApproverRoles((initial.approver_roles || []).join(", "));
      setApproverEmails((initial.approver_emails || []).join(", "));
      setAllowSelfApprove(!!initial.allow_self_approve);
      setEnabled(initial.enabled !== false);
      setTimeoutSeconds(
        initial.timeout_seconds ? String(initial.timeout_seconds) : ""
      );
      setPriority(String(initial.priority ?? 0));
      return;
    }
    setName("");
    setActionType("create_maintenance");
    setResourceType("");
    setApproverRoles("admin");
    setApproverEmails("");
    setAllowSelfApprove(false);
    setEnabled(true);
    setTimeoutSeconds("");
    setPriority("0");
  }, [initial]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSaving(true);
    try {
      const timeout = timeoutSeconds.trim()
        ? Number(timeoutSeconds)
        : undefined;
      const cel = formatApprovalCelQuery(query);
      await onSubmit({
        name,
        action_type: actionType,
        resource_type: resourceType || undefined,
        cel: cel || undefined,
        enabled,
        approver_roles: approverRoles
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
        approver_emails: approverEmails
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
        allow_self_approve: allowSelfApprove,
        timeout_seconds: timeout && timeout > 0 ? timeout : undefined,
        priority: Number(priority) || 0,
        min_approvals: 1,
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <form className="flex flex-col gap-3" onSubmit={handleSubmit}>
      <div>
        <Text>Name</Text>
        <TextInput
          required
          value={name}
          onValueChange={setName}
          placeholder="e.g. Long maintenance windows"
        />
      </div>
      <div>
        <Text>Action type</Text>
        <Select
          value={actionType}
          onValueChange={(value) =>
            setActionType((value as ApprovalActionType) || "custom")
          }
        >
          {APPROVAL_ACTION_TYPES.map((type) => (
            <SelectItem key={type} value={type}>
              {type}
            </SelectItem>
          ))}
        </Select>
      </div>
      <div>
        <Text>Resource type (optional)</Text>
        <TextInput
          value={resourceType}
          onValueChange={setResourceType}
          placeholder="workflow, maintenance, provider..."
        />
      </div>
      <ApprovalPolicyCelFilter
        value={initial?.cel || ""}
        query={query}
        onChange={setQuery}
      />
      <div>
        <Text>Approver roles (comma-separated)</Text>
        <TextInput value={approverRoles} onValueChange={setApproverRoles} />
      </div>
      <div>
        <Text>Approver emails (comma-separated)</Text>
        <TextInput value={approverEmails} onValueChange={setApproverEmails} />
      </div>
      <div>
        <Text>Timeout seconds (optional)</Text>
        <TextInput value={timeoutSeconds} onValueChange={setTimeoutSeconds} />
      </div>
      <div>
        <Text>Priority</Text>
        <TextInput value={priority} onValueChange={setPriority} />
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={allowSelfApprove}
          onChange={(event) => setAllowSelfApprove(event.target.checked)}
        />
        Allow self-approve
      </label>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(event) => setEnabled(event.target.checked)}
        />
        Enabled
      </label>
      <div className="flex gap-2 justify-end mt-2">
        <Button variant="secondary" type="button" onClick={onCancel}>
          Cancel
        </Button>
        <Button color="orange" type="submit" loading={isSaving}>
          {initial ? "Save" : "Create policy"}
        </Button>
      </div>
    </form>
  );
}
