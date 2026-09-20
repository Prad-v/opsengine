"use client";

import { useState } from "react";
import {
  Badge,
  Button,
  Callout,
  Text,
  Textarea,
  Title,
} from "@tremor/react";
import type { ApprovalRequest } from "../model/types";

interface ApprovalDetailDrawerProps {
  request: ApprovalRequest;
  onApprove: (comment?: string) => Promise<void>;
  onReject: (comment?: string) => Promise<void>;
  onCancel: () => Promise<void>;
  onClose: () => void;
}

export function ApprovalDetailDrawer({
  request,
  onApprove,
  onReject,
  onCancel,
  onClose,
}: ApprovalDetailDrawerProps) {
  const [comment, setComment] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const isPending = request.status === "pending";

  const run = async (action: () => Promise<void>) => {
    setIsSaving(true);
    try {
      await action();
      onClose();
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="flex flex-col gap-3 p-2">
      <div>
        <Title>{request.title}</Title>
        <Text className="mt-1">{request.summary || "No summary"}</Text>
      </div>
      <div className="flex flex-wrap gap-2">
        <Badge color={isPending ? "orange" : "gray"}>{request.status}</Badge>
        <Badge color="gray">{request.action_type}</Badge>
        {request.resource_type ? (
          <Badge color="gray">{request.resource_type}</Badge>
        ) : null}
      </div>
      <Text className="text-xs">
        Requested by {request.requested_by} at {request.requested_at}
      </Text>
      {request.decided_by ? (
        <Text className="text-xs">
          Decided by {request.decided_by}
          {request.decision_comment ? `: ${request.decision_comment}` : ""}
        </Text>
      ) : null}
      <pre className="text-xs bg-gray-50 border rounded p-2 overflow-auto max-h-56">
        {JSON.stringify(
          {
            payload: request.payload,
            context: request.context,
            callback: request.callback,
            result: request.result,
          },
          null,
          2
        )}
      </pre>
      {isPending ? (
        <>
          <Textarea
            value={comment}
            onValueChange={setComment}
            placeholder="Optional comment"
          />
          <div className="flex flex-wrap gap-2 justify-end">
            <Button variant="secondary" type="button" onClick={onClose}>
              Close
            </Button>
            <Button
              variant="secondary"
              type="button"
              loading={isSaving}
              onClick={() => run(() => onCancel())}
            >
              Cancel
            </Button>
            <Button
              color="red"
              type="button"
              loading={isSaving}
              onClick={() => run(() => onReject(comment || undefined))}
            >
              Reject
            </Button>
            <Button
              color="orange"
              type="button"
              loading={isSaving}
              onClick={() => run(() => onApprove(comment || undefined))}
            >
              Approve
            </Button>
          </div>
        </>
      ) : (
        <Callout title="This request is no longer pending" color="gray">
          <Button variant="secondary" type="button" onClick={onClose}>
            Close
          </Button>
        </Callout>
      )}
    </div>
  );
}
