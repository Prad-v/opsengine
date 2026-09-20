"use client";

import { useEffect, useMemo, useState } from "react";
import { Button, Select, SelectItem, Text } from "@tremor/react";
import Link from "next/link";
import { showErrorToast, showSuccessToast } from "@/shared/ui";
import { useWorkflowActions } from "@/entities/workflows/model";
import type {
  AlertCatalogAutoRunOn,
  AlertCatalogEntry,
} from "@/features/catalog/alert-code";
import type { Workflow } from "@/shared/api/workflows";
import { buildNotifyWorkflowYaml } from "../../model/onboardingTemplates";

const AUTO_RUN_OPTIONS: { id: AlertCatalogAutoRunOn; label: string }[] = [
  { id: "both", label: "Alert and incident" },
  { id: "alert", label: "Alert only" },
  { id: "incident", label: "Incident only" },
];

const CREATE_NEW_VALUE = "__create_notify__";

interface WorkflowStepProps {
  selectedCode: string;
  catalog: AlertCatalogEntry[];
  workflows: Workflow[];
  workflowId: string;
  onSelectCode: (code: string) => void;
  onWorkflowCreated: (workflowId: string) => void;
  onAttach: (
    entry: AlertCatalogEntry,
    workflowId: string,
    autoRunOn: AlertCatalogAutoRunOn
  ) => Promise<unknown>;
}

function workflowName(workflow: Workflow): string {
  return workflow.name || workflow.workflow_raw_id || workflow.id;
}

export function WorkflowStep({
  selectedCode,
  catalog,
  workflows,
  workflowId,
  onSelectCode,
  onWorkflowCreated,
  onAttach,
}: WorkflowStepProps) {
  const { createWorkflow } = useWorkflowActions();
  const [pickedWorkflowId, setPickedWorkflowId] = useState(
    workflowId || CREATE_NEW_VALUE
  );
  const [autoRunOn, setAutoRunOn] = useState<AlertCatalogAutoRunOn>("both");
  const [isSaving, setIsSaving] = useState(false);

  const selectedEntry = catalog.find((entry) => entry.code === selectedCode);
  const yaml = useMemo(
    () =>
      buildNotifyWorkflowYaml({
        code: selectedCode || "HIGH_CPU",
        providerType: "console",
      }),
    [selectedCode]
  );

  const workflowById = useMemo(() => {
    const map = new Map<string, Workflow>();
    for (const workflow of workflows) {
      map.set(workflow.id, workflow);
      if (workflow.workflow_raw_id) {
        map.set(workflow.workflow_raw_id, workflow);
      }
    }
    return map;
  }, [workflows]);

  const attachedWorkflow =
    workflowById.get(selectedEntry?.keep_workflow_id || "") ||
    workflowById.get(workflowId);

  useEffect(() => {
    const attachedId = selectedEntry?.keep_workflow_id || workflowId;
    if (attachedId && workflowById.has(attachedId)) {
      setPickedWorkflowId(attachedId);
      return;
    }
    if (!pickedWorkflowId) {
      setPickedWorkflowId(
        workflows.length > 0 ? workflows[0].id : CREATE_NEW_VALUE
      );
    }
  }, [
    selectedEntry?.keep_workflow_id,
    workflowId,
    workflowById,
    workflows,
    pickedWorkflowId,
  ]);

  const handleAttach = async () => {
    if (!selectedEntry) {
      showErrorToast(
        new Error("Select an alert code first"),
        "Register an alert code before attaching a workflow"
      );
      return;
    }
    setIsSaving(true);
    try {
      let id = pickedWorkflowId;
      if (id === CREATE_NEW_VALUE) {
        const result = await createWorkflow(yaml);
        if (!result?.workflow_id) {
          throw new Error("Workflow was not created");
        }
        id = result.workflow_id;
        setPickedWorkflowId(id);
      }
      await onAttach(selectedEntry, id, autoRunOn);
      onWorkflowCreated(id);
      const name = workflowById.get(id)?.name || `Notify on ${selectedCode}`;
      showSuccessToast(`Attached ${name} to ${selectedEntry.code}`);
    } catch (error) {
      showErrorToast(error, "Failed to attach workflow");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-4" data-testid="workflow-attach-step">
      <Text>
        Select a workflow by name and attach it to this alert code. It can
        auto-run for the alert, the correlated incident, or both.
      </Text>

      {catalog.length > 0 && (
        <div>
          <Text>Alert code</Text>
          <Select
            value={selectedCode}
            onValueChange={onSelectCode}
            placeholder="Select a registered code"
          >
            {catalog.map((entry) => (
              <SelectItem key={entry.id} value={entry.code}>
                {entry.name ? `${entry.code} — ${entry.name}` : entry.code}
              </SelectItem>
            ))}
          </Select>
        </div>
      )}

      <div>
        <Text>Workflow name</Text>
        <Select
          enableClear={false}
          value={pickedWorkflowId}
          onValueChange={setPickedWorkflowId}
          placeholder="Select a workflow"
        >
          <SelectItem value={CREATE_NEW_VALUE}>
            {selectedCode
              ? `Create “Notify on ${selectedCode}”`
              : "Create a notify workflow for this code"}
          </SelectItem>
          {workflows.map((workflow) => (
            <SelectItem key={workflow.id} value={workflow.id}>
              {workflowName(workflow)}
            </SelectItem>
          ))}
        </Select>
      </div>

      <div>
        <Text>Auto-run on</Text>
        <Select
          value={autoRunOn}
          onValueChange={(value) =>
            setAutoRunOn((value as AlertCatalogAutoRunOn) || "both")
          }
        >
          {AUTO_RUN_OPTIONS.map((option) => (
            <SelectItem key={option.id} value={option.id}>
              {option.label}
            </SelectItem>
          ))}
        </Select>
      </div>

      <Button
        color="orange"
        disabled={!selectedEntry}
        loading={isSaving}
        onClick={handleAttach}
      >
        {pickedWorkflowId === CREATE_NEW_VALUE
          ? "Create and attach"
          : "Attach workflow"}
      </Button>

      {selectedEntry?.keep_workflow_id && (
        <Text className="text-emerald-700" data-testid="attached-workflow">
          {selectedEntry.code} auto-runs{" "}
          <Link
            className="underline"
            href={`/workflows/${selectedEntry.keep_workflow_id}`}
          >
            {attachedWorkflow
              ? workflowName(attachedWorkflow)
              : "workflow"}
          </Link>{" "}
          on {selectedEntry.auto_run_on}.
        </Text>
      )}
    </div>
  );
}
