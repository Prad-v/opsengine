"use client";

import type { ReactNode } from "react";
import { Badge, Button, Text, Title } from "@tremor/react";
import { Drawer } from "@/shared/ui/Drawer";
import { DynamicImageProviderIcon } from "@/components/ui";
import type { TemporalCatalogEntry } from "../model/types";

interface TemporalWorkflowViewDrawerProps {
  entry: TemporalCatalogEntry | null;
  isOpen: boolean;
  onClose: () => void;
  onEdit: (entry: TemporalCatalogEntry) => void;
  onDelete: (entry: TemporalCatalogEntry) => void;
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <Text className="text-xs text-tremor-content mb-1">{label}</Text>
      <div className="text-sm text-tremor-content-strong">{children}</div>
    </div>
  );
}

export function TemporalWorkflowViewDrawer({
  entry,
  isOpen,
  onClose,
  onEdit,
  onDelete,
}: TemporalWorkflowViewDrawerProps) {
  return (
    <Drawer isOpen={isOpen} onClose={onClose}>
      {entry ? (
        <div className="space-y-4 p-2" data-testid="temporal-workflow-view">
          <div className="flex items-start justify-between gap-3">
            <div>
              <Title>{entry.name}</Title>
              <Text className="mt-1">
                <code>{entry.catalog_key}</code>
                {entry.disabled ? " · disabled" : " · active"}
              </Text>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                color="orange"
                size="xs"
                onClick={() => onEdit(entry)}
              >
                Edit
              </Button>
              <Button
                variant="secondary"
                color="red"
                size="xs"
                onClick={() => onDelete(entry)}
              >
                Delete
              </Button>
            </div>
          </div>

          {entry.description ? <Text>{entry.description}</Text> : null}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Field label="Workflow type">
              <Badge color="indigo">{entry.workflow_type}</Badge>
            </Field>
            <Field label="Task queue">{entry.task_queue}</Field>
            <Field label="Provider">
              <div className="flex items-center gap-2">
                <DynamicImageProviderIcon
                  providerType="temporal"
                  width={20}
                  height={20}
                />
                <span>{entry.provider_name || entry.provider_id}</span>
              </div>
            </Field>
            <Field label="Status">
              {entry.disabled ? (
                <Badge color="gray">Disabled</Badge>
              ) : (
                <Badge color="emerald">Enabled</Badge>
              )}
            </Field>
          </div>

          <Field label="Input mapping">
            <pre className="mt-1 max-h-56 overflow-auto rounded border bg-gray-50 p-2 text-xs">
              {JSON.stringify(entry.input_mapping || {}, null, 2)}
            </pre>
          </Field>

          {entry.workflow_id_template ? (
            <Field label="Workflow id template">
              <code className="text-xs">{entry.workflow_id_template}</code>
            </Field>
          ) : null}

          <div className="space-y-1 border-t border-gray-100 pt-3 text-xs text-tremor-content">
            {entry.created_by ? (
              <Text>Created by {entry.created_by}</Text>
            ) : null}
            {entry.updated_by ? (
              <Text>Updated by {entry.updated_by}</Text>
            ) : null}
          </div>

          <div className="flex justify-end">
            <Button variant="secondary" size="xs" onClick={onClose}>
              Close
            </Button>
          </div>
        </div>
      ) : null}
    </Drawer>
  );
}
