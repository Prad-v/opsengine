"use client";

import { useState } from "react";
import { Button, Card, Title, Text } from "@tremor/react";
import { Drawer } from "@/shared/ui/Drawer";
import { showErrorToast, showSuccessToast } from "@/shared/ui";
import { isApprovalPending } from "@/features/approvals";
import { useAlertCatalog } from "../model/useAlertCatalog";
import type { AlertCatalogEntry, AlertCatalogEntryInput } from "../model/types";
import { AlertCatalogTable } from "./AlertCatalogTable";
import { AlertCatalogForm } from "./AlertCatalogForm";

export function AlertCatalogPage() {
  const {
    catalog,
    error,
    isLoading,
    mutate,
    createEntry,
    updateEntry,
    deleteEntry,
  } = useAlertCatalog();
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<AlertCatalogEntry | null>(null);

  const openCreate = () => {
    setEditing(null);
    setIsDrawerOpen(true);
  };

  const openEdit = (entry: AlertCatalogEntry) => {
    setEditing(entry);
    setIsDrawerOpen(true);
  };

  const closeDrawer = () => {
    setIsDrawerOpen(false);
    setEditing(null);
  };

  const handleSubmit = async (body: AlertCatalogEntryInput) => {
    try {
      if (editing) {
        await updateEntry(editing.id, body);
        showSuccessToast("Alert code updated");
      } else {
        await createEntry(body);
        showSuccessToast("Alert code registered");
      }
      closeDrawer();
    } catch (err) {
      showErrorToast(err, "Failed to save alert code");
      throw err;
    }
  };

  const handleDelete = async (entry: AlertCatalogEntry) => {
    if (!confirm(`Delete alert code "${entry.name}" (${entry.code})?`)) {
      return;
    }
    try {
      const result = await deleteEntry(entry.id);
      showSuccessToast(
        isApprovalPending(result)
          ? "Delete submitted for approval"
          : "Alert code deleted"
      );
    } catch (err) {
      showErrorToast(err, "Failed to delete alert code");
    }
  };

  return (
    <>
      <Card>
        <div className="flex items-start justify-between gap-4 mb-3">
          <div>
            <Title>Alert codes</Title>
            <Text className="mt-1">
              Reserved <code>labels.code</code> is the stable key for runbooks
              and automation. Name and description stay free-form. A workflow
              can run for the alert, the correlated incident, or both.
            </Text>
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" size="xs" onClick={() => mutate()}>
              Refresh
            </Button>
            <Button color="orange" size="xs" onClick={openCreate}>
              Register code
            </Button>
          </div>
        </div>

        <AlertCatalogTable
          catalog={catalog}
          isLoading={isLoading}
          error={error}
          emptyMessage={
            <>
              No alert codes yet. Click <strong>Register code</strong> to attach
              a runbook and optionally auto-run a Keep workflow.
            </>
          }
          renderActions={(entry) => (
            <>
              <Button
                size="xs"
                variant="secondary"
                onClick={() => openEdit(entry)}
              >
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
            {editing ? "Edit alert code" : "Register alert code"}
          </Title>
          <AlertCatalogForm
            initial={editing}
            onSubmit={handleSubmit}
            onCancel={closeDrawer}
          />
        </div>
      </Drawer>
    </>
  );
}
