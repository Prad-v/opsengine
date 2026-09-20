"use client";

import { useState } from "react";
import {
  Button,
  Card,
  Title,
  Text,
} from "@tremor/react";
import { Drawer } from "@/shared/ui/Drawer";
import { showErrorToast, showSuccessToast } from "@/shared/ui";
import { isApprovalPending } from "@/features/approvals";
import { useTemporalWorkflowCatalog } from "../model/useTemporalWorkflowCatalog";
import type {
  TemporalCatalogEntry,
  TemporalCatalogEntryInput,
} from "../model/types";
import { TemporalCatalogTable } from "./TemporalCatalogTable";
import { TemporalWorkflowForm } from "./TemporalWorkflowForm";
import { TemporalWorkflowViewDrawer } from "./TemporalWorkflowViewDrawer";

export function TemporalWorkflowCatalogPage() {
  const {
    catalog,
    error,
    isLoading,
    mutate,
    createEntry,
    updateEntry,
    deleteEntry,
  } = useTemporalWorkflowCatalog();
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editing, setEditing] = useState<TemporalCatalogEntry | null>(null);
  const [viewing, setViewing] = useState<TemporalCatalogEntry | null>(null);

  const openCreate = () => {
    setViewing(null);
    setEditing(null);
    setIsFormOpen(true);
  };

  const openView = (entry: TemporalCatalogEntry) => {
    setIsFormOpen(false);
    setEditing(null);
    setViewing(entry);
  };

  const openEdit = (entry: TemporalCatalogEntry) => {
    setViewing(null);
    setEditing(entry);
    setIsFormOpen(true);
  };

  const closeForm = () => {
    setIsFormOpen(false);
    setEditing(null);
  };

  const closeView = () => {
    setViewing(null);
  };

  const handleSubmit = async (body: TemporalCatalogEntryInput) => {
    try {
      if (editing) {
        await updateEntry(editing.id, body);
        showSuccessToast("Temporal workflow updated");
      } else {
        await createEntry(body);
        showSuccessToast("Temporal workflow registered");
      }
      closeForm();
    } catch (err) {
      showErrorToast(err, "Failed to save Temporal workflow");
      throw err;
    }
  };

  const handleDelete = async (entry: TemporalCatalogEntry) => {
    if (
      !confirm(
        `Delete catalog entry "${entry.name}" (${entry.catalog_key})?`
      )
    ) {
      return;
    }
    try {
      const result = await deleteEntry(entry.id);
      showSuccessToast(
        isApprovalPending(result)
          ? "Delete submitted for approval"
          : "Temporal workflow deleted"
      );
      if (viewing?.id === entry.id) {
        closeView();
      }
      if (editing?.id === entry.id) {
        closeForm();
      }
    } catch (err) {
      showErrorToast(err, "Failed to delete Temporal workflow");
    }
  };

  return (
    <>
      <Card>
        <div className="flex items-start justify-between gap-4 mb-3">
          <div>
            <Title>Temporal workflow catalog</Title>
            <Text className="mt-1">
              Register Temporal workflows here. Incidents can then start and
              link them from the Workflows tab.
            </Text>
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" size="xs" onClick={() => mutate()}>
              Refresh
            </Button>
            <Button color="orange" size="xs" onClick={openCreate}>
              Register workflow
            </Button>
          </div>
        </div>

        <TemporalCatalogTable
          catalog={catalog}
          isLoading={isLoading}
          error={error}
          emptyMessage={
            <>
              No workflows registered yet. Click{" "}
              <strong>Register workflow</strong> to add one. You need a Temporal
              provider connected under Providers first.
            </>
          }
          onView={openView}
          renderActions={(entry) => (
            <>
              <Button
                size="xs"
                variant="secondary"
                onClick={(event) => {
                  event.stopPropagation();
                  openView(entry);
                }}
              >
                View
              </Button>
              <Button
                size="xs"
                variant="secondary"
                onClick={(event) => {
                  event.stopPropagation();
                  openEdit(entry);
                }}
              >
                Edit
              </Button>
              <Button
                size="xs"
                variant="secondary"
                color="red"
                onClick={(event) => {
                  event.stopPropagation();
                  handleDelete(entry);
                }}
              >
                Delete
              </Button>
            </>
          )}
        />
      </Card>

      <TemporalWorkflowViewDrawer
        entry={viewing}
        isOpen={!!viewing}
        onClose={closeView}
        onEdit={openEdit}
        onDelete={handleDelete}
      />

      <Drawer isOpen={isFormOpen} onClose={closeForm}>
        <div className="p-2">
          <Title className="mb-4">
            {editing ? "Edit Temporal workflow" : "Register Temporal workflow"}
          </Title>
          <TemporalWorkflowForm
            initial={editing}
            onSubmit={handleSubmit}
            onCancel={closeForm}
          />
        </div>
      </Drawer>
    </>
  );
}
