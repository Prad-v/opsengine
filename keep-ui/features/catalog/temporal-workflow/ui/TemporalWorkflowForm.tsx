"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  Button,
  Select,
  SelectItem,
  Text,
  TextInput,
  Textarea,
} from "@tremor/react";
import { useProviders } from "@/utils/hooks/useProviders";
import { showErrorToast } from "@/shared/ui";
import type {
  TemporalCatalogEntry,
  TemporalCatalogEntryInput,
} from "../model/types";

interface TemporalWorkflowFormProps {
  initial?: TemporalCatalogEntry | null;
  onSubmit: (body: TemporalCatalogEntryInput) => Promise<void>;
  onCancel: () => void;
}

const DEFAULT_MAPPING = `{
  "incident_id": "id",
  "name": "name",
  "severity": "severity",
  "status": "status",
  "services": "services"
}`;

export function TemporalWorkflowForm({
  initial,
  onSubmit,
  onCancel,
}: TemporalWorkflowFormProps) {
  const { data: providersData } = useProviders();
  const temporalProviders = useMemo(
    () =>
      (providersData?.installed_providers ?? []).filter(
        (provider) => provider.type === "temporal"
      ),
    [providersData?.installed_providers]
  );

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [workflowType, setWorkflowType] = useState("");
  const [taskQueue, setTaskQueue] = useState("");
  const [inputMappingText, setInputMappingText] = useState(DEFAULT_MAPPING);
  const [providerId, setProviderId] = useState("");
  const [disabled, setDisabled] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (initial) {
      setName(initial.name);
      setDescription(initial.description || "");
      setWorkflowType(initial.workflow_type);
      setTaskQueue(initial.task_queue);
      setInputMappingText(
        JSON.stringify(initial.input_mapping || {}, null, 2)
      );
      setProviderId(initial.provider_id);
      setDisabled(!!initial.disabled);
      return;
    }
    setName("");
    setDescription("");
    setWorkflowType("");
    setTaskQueue("");
    setInputMappingText(DEFAULT_MAPPING);
    setProviderId(temporalProviders[0]?.id || "");
    setDisabled(false);
  }, [initial, temporalProviders]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    let inputMapping: Record<string, string> = {};
    try {
      const parsed = JSON.parse(inputMappingText || "{}");
      if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("input_mapping must be a JSON object");
      }
      inputMapping = Object.fromEntries(
        Object.entries(parsed).map(([key, value]) => [key, String(value)])
      );
    } catch (err) {
      showErrorToast(err, "Invalid input mapping JSON");
      return;
    }

    if (!providerId) {
      showErrorToast(new Error("Select a Temporal provider"), "Provider required");
      return;
    }

    setIsSaving(true);
    try {
      await onSubmit({
        // Keep existing key on edit; create path lets the API generate from name.
        catalog_key: initial?.catalog_key,
        name: name.trim(),
        description: description.trim() || undefined,
        workflow_type: workflowType.trim(),
        task_queue: taskQueue.trim(),
        input_mapping: inputMapping,
        provider_id: providerId,
        disabled,
      });
    } finally {
      setIsSaving(false);
    }
  };

  if (temporalProviders.length === 0) {
    return (
      <Text>
        Install a Temporal provider under Providers before registering
        workflows.
      </Text>
    );
  }

  return (
    <form className="flex flex-col gap-3" onSubmit={handleSubmit}>
      <div>
        <Text className="mb-1">Name</Text>
        <TextInput
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Remediate Incident"
        />
        {initial?.catalog_key ? (
          <Text className="mt-1 text-xs text-tremor-content">
            Catalog key: <code>{initial.catalog_key}</code>
          </Text>
        ) : (
          <Text className="mt-1 text-xs text-tremor-content">
            Catalog key and workflow id are generated automatically.
          </Text>
        )}
      </div>
      <div>
        <Text className="mb-1">Description</Text>
        <Textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Optional description"
        />
      </div>
      <div>
        <Text className="mb-1">Workflow type</Text>
        <TextInput
          required
          value={workflowType}
          onChange={(e) => setWorkflowType(e.target.value)}
          placeholder="RemediateIncident"
        />
      </div>
      <div>
        <Text className="mb-1">Task queue</Text>
        <TextInput
          required
          value={taskQueue}
          onChange={(e) => setTaskQueue(e.target.value)}
          placeholder="keep-ops"
        />
      </div>
      <div>
        <Text className="mb-1">Temporal provider</Text>
        <Select value={providerId} onValueChange={setProviderId}>
          {temporalProviders.map((provider) => (
            <SelectItem key={provider.id} value={provider.id}>
              {provider.details?.name || provider.display_name || provider.id}
            </SelectItem>
          ))}
        </Select>
      </div>
      <div>
        <Text className="mb-1">Input mapping (JSON)</Text>
        <Text className="mb-1 text-xs text-tremor-content">
          Maps Temporal workflow input keys to incident fields.
        </Text>
        <Textarea
          rows={8}
          value={inputMappingText}
          onChange={(e) => setInputMappingText(e.target.value)}
        />
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={disabled}
          onChange={(e) => setDisabled(e.target.checked)}
        />
        Disabled
      </label>
      <div className="flex gap-2 justify-end mt-2">
        <Button type="button" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" color="orange" loading={isSaving}>
          {initial ? "Save" : "Register"}
        </Button>
      </div>
    </form>
  );
}
