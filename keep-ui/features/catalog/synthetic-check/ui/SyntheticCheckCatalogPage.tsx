"use client";

import { useState } from "react";
import { Button, Card, Title, Text } from "@tremor/react";
import { Drawer } from "@/shared/ui/Drawer";
import { showErrorToast, showSuccessToast } from "@/shared/ui";
import { isApprovalPending } from "@/features/approvals";
import { useSyntheticChecks } from "../model/useSyntheticChecks";
import type { SyntheticCheck, SyntheticCheckInput } from "../model/types";
import { SyntheticCheckTable } from "./SyntheticCheckTable";
import { SyntheticCheckForm } from "./SyntheticCheckForm";

export function SyntheticCheckCatalogPage() {
  const {
    checks,
    error,
    isLoading,
    mutate,
    createCheck,
    updateCheck,
    deleteCheck,
    runCheck,
  } = useSyntheticChecks();
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<SyntheticCheck | null>(null);
  const [runningId, setRunningId] = useState<number | null>(null);

  const openCreate = () => {
    setEditing(null);
    setIsDrawerOpen(true);
  };

  const openEdit = (entry: SyntheticCheck) => {
    setEditing(entry);
    setIsDrawerOpen(true);
  };

  const closeDrawer = () => {
    setIsDrawerOpen(false);
    setEditing(null);
  };

  const handleSubmit = async (body: SyntheticCheckInput) => {
    try {
      if (editing) {
        await updateCheck(editing.id, body);
        showSuccessToast("Synthetic check updated");
      } else {
        await createCheck(body);
        showSuccessToast("Synthetic check created");
      }
      closeDrawer();
    } catch (err) {
      showErrorToast(err, "Failed to save synthetic check");
      throw err;
    }
  };

  const handleDelete = async (entry: SyntheticCheck) => {
    if (!confirm(`Delete synthetic check "${entry.name}" (${entry.check_key})?`)) {
      return;
    }
    try {
      const result = await deleteCheck(entry.id);
      showSuccessToast(
        isApprovalPending(result)
          ? "Delete submitted for approval"
          : "Synthetic check deleted"
      );
    } catch (err) {
      showErrorToast(err, "Failed to delete synthetic check");
    }
  };

  const handleRun = async (entry: SyntheticCheck) => {
    setRunningId(entry.id);
    try {
      const result = await runCheck(entry.id);
      showSuccessToast(
        `Started ${result.workflow_type}: ${result.workflow_id}`
      );
    } catch (err) {
      showErrorToast(err, "Failed to run synthetic check");
    } finally {
      setRunningId(null);
    }
  };

  return (
    <>
      <Card>
        <div className="flex items-start justify-between gap-4 mb-3">
          <div>
            <Title>Synthetic checks</Title>
            <Text className="mt-1">
              Blackbox-style HTTP, TCP, and DNS probes scheduled via Temporal
              (<code>keep-synth</code>). Failures post alerts to Keep.
            </Text>
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" size="xs" onClick={() => mutate()}>
              Refresh
            </Button>
            <Button color="orange" size="xs" onClick={openCreate}>
              New check
            </Button>
          </div>
        </div>

        <SyntheticCheckTable
          checks={checks}
          isLoading={isLoading}
          error={error}
          emptyMessage={
            <>
              No checks yet. Click <strong>New check</strong>, or seed the AI
              datacenter pack with <code>make register-ai-dc-synthetic-checks</code>.
              Connect a Temporal provider and run <code>make synthetic-checks</code>
              so the worker can execute probes.
            </>
          }
          renderActions={(entry) => (
            <>
              <Button
                size="xs"
                variant="secondary"
                loading={runningId === entry.id}
                onClick={() => handleRun(entry)}
              >
                Run now
              </Button>
              <Button size="xs" variant="secondary" onClick={() => openEdit(entry)}>
                Edit
              </Button>
              <Button
                size="xs"
                variant="secondary"
                color="red"
                onClick={() => handleDelete(entry)}
              >
                Delete
              </Button>
            </>
          )}
        />
      </Card>

      <Drawer isOpen={isDrawerOpen} onClose={closeDrawer}>
        <div className="p-2">
          <Title className="mb-4">
            {editing ? "Edit synthetic check" : "Create synthetic check"}
          </Title>
          <SyntheticCheckForm
            initial={editing}
            onSubmit={handleSubmit}
            onCancel={closeDrawer}
          />
        </div>
      </Drawer>
    </>
  );
}
