"use client";

import { useState } from "react";
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
import { useApprovalPolicies } from "../model/useApprovalPolicies";
import type { ApprovalPolicy, ApprovalPolicyInput } from "../model/types";
import { ApprovalPolicyForm } from "./ApprovalPolicyForm";

export function ApprovalPoliciesPage() {
  const {
    policies,
    isLoading,
    error,
    createPolicy,
    updatePolicy,
    deletePolicy,
  } = useApprovalPolicies();
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<ApprovalPolicy | null>(null);

  const closeDrawer = () => {
    setIsDrawerOpen(false);
    setEditing(null);
  };

  const handleSubmit = async (body: ApprovalPolicyInput) => {
    if (editing) {
      await updatePolicy(editing.id, body);
    } else {
      await createPolicy(body);
    }
    closeDrawer();
  };

  return (
    <>
      <Card>
        <div className="flex items-start justify-between gap-4 mb-3">
          <div>
            <Title>Approval policies</Title>
            <Text className="mt-1">
              When a policy matches an action (CEL + action type), Keep creates
              a pending request instead of executing immediately.
            </Text>
          </div>
          <Button
            color="orange"
            size="xs"
            onClick={() => {
              setEditing(null);
              setIsDrawerOpen(true);
            }}
          >
            New policy
          </Button>
        </div>
        {error ? (
          <Text color="red">Failed to load policies</Text>
        ) : isLoading ? (
          <Text>Loading...</Text>
        ) : policies.length === 0 ? (
          <Text>No policies yet. Actions run immediately until you add one.</Text>
        ) : (
          <Table>
            <TableHead>
              <TableRow>
                <TableHeaderCell>Name</TableHeaderCell>
                <TableHeaderCell>Action</TableHeaderCell>
                <TableHeaderCell>CEL</TableHeaderCell>
                <TableHeaderCell>Enabled</TableHeaderCell>
                <TableHeaderCell></TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {policies.map((policy) => (
                <TableRow key={policy.id}>
                  <TableCell>{policy.name}</TableCell>
                  <TableCell>
                    <Badge color="gray">{policy.action_type}</Badge>
                  </TableCell>
                  <TableCell className="max-w-xs truncate">
                    {policy.cel || "true"}
                  </TableCell>
                  <TableCell>
                    <Badge color={policy.enabled ? "green" : "gray"}>
                      {policy.enabled ? "on" : "off"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-2">
                      <Button
                        size="xs"
                        variant="secondary"
                        onClick={() => {
                          setEditing(policy);
                          setIsDrawerOpen(true);
                        }}
                      >
                        Edit
                      </Button>
                      <Button
                        size="xs"
                        variant="secondary"
                        color="red"
                        onClick={() => {
                          if (
                            confirm(`Delete approval policy "${policy.name}"?`)
                          ) {
                            deletePolicy(policy.id);
                          }
                        }}
                      >
                        Delete
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>
      <Drawer isOpen={isDrawerOpen} onClose={closeDrawer}>
        <div className="p-2">
          <Title className="mb-4">
            {editing ? "Edit policy" : "New approval policy"}
          </Title>
          <ApprovalPolicyForm
            initial={editing}
            onSubmit={handleSubmit}
            onCancel={closeDrawer}
          />
        </div>
      </Drawer>
    </>
  );
}
