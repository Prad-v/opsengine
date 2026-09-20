"use client";

import { useEffect, useState } from "react";
import {
  Badge,
  Button,
  Card,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  Text,
  Title,
} from "@tremor/react";
import { Drawer } from "@/shared/ui/Drawer";
import { useApprovals } from "../model/useApprovals";
import { useApprovalActions } from "../model/useApprovalActions";
import type { ApprovalRequest } from "../model/types";
import { ApprovalDetailDrawer } from "./ApprovalDetailDrawer";

export function ApprovalsInbox() {
  const { requests, isLoading, error, mutate, subscribe, unsubscribe } =
    useApprovals({ status: "pending" });
  const { approve, reject, cancel } = useApprovalActions();
  const [selected, setSelected] = useState<ApprovalRequest | null>(null);

  useEffect(() => {
    subscribe();
    return () => unsubscribe();
  }, [subscribe, unsubscribe]);

  return (
    <>
      <Card>
        <div className="flex items-start justify-between gap-4 mb-3">
          <div>
            <Title>Approvals</Title>
            <Text className="mt-1">
              Pending changes wait here until an authorized user approves or
              rejects them. Matching policies are opt-in; without a policy the
              original action still runs immediately.
            </Text>
          </div>
          <Button variant="secondary" size="xs" onClick={() => mutate()}>
            Refresh
          </Button>
        </div>
        {error ? (
          <Text color="red">
            Failed to load approval requests
            {error instanceof Error && error.message
              ? `: ${error.message}`
              : ""}
          </Text>
        ) : isLoading ? (
          <Text>Loading...</Text>
        ) : requests.length === 0 ? (
          <Text>No pending approvals.</Text>
        ) : (
          <Table>
            <TableHead>
              <TableRow>
                <TableHeaderCell>Title</TableHeaderCell>
                <TableHeaderCell>Action</TableHeaderCell>
                <TableHeaderCell>Requested by</TableHeaderCell>
                <TableHeaderCell>Status</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {requests.map((request) => (
                <TableRow
                  key={request.id}
                  className="cursor-pointer"
                  onClick={() => setSelected(request)}
                >
                  <TableCell>{request.title}</TableCell>
                  <TableCell>
                    <Badge color="gray">{request.action_type}</Badge>
                  </TableCell>
                  <TableCell>{request.requested_by}</TableCell>
                  <TableCell>
                    <Badge color="orange">{request.status}</Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>
      <Drawer isOpen={!!selected} onClose={() => setSelected(null)}>
        {selected ? (
          <ApprovalDetailDrawer
            request={selected}
            onApprove={(comment) => approve(selected.id, comment).then(() => undefined)}
            onReject={(comment) => reject(selected.id, comment).then(() => undefined)}
            onCancel={() => cancel(selected.id).then(() => undefined)}
            onClose={() => setSelected(null)}
          />
        ) : null}
      </Drawer>
    </>
  );
}
