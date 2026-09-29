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
import { TbSparkles } from "react-icons/tb";
import { MultiValue } from "react-select";
import CreatableMultiSelect from "@/components/ui/CreatableMultiSelect";
import { useWorkflows } from "@/entities/workflows/model";
import { useAISettings } from "@/features/settings/ai";
import { showErrorToast, showSuccessToast } from "@/shared/ui";
import { useAlertCatalog } from "../model/useAlertCatalog";
import type {
  AlertCatalogAutoRunOn,
  AlertCatalogEntry,
  AlertCatalogEntryInput,
} from "../model/types";

interface AlertCatalogFormProps {
  initial?: AlertCatalogEntry | null;
  onSubmit: (body: AlertCatalogEntryInput) => Promise<void>;
  onCancel: () => void;
  showWorkflowFields?: boolean;
  submitLabel?: string;
  suggestedTags?: string[];
}

type TagOption = { value: string; label: string };

const AUTO_RUN_OPTIONS: { id: AlertCatalogAutoRunOn; label: string }[] = [
  { id: "none", label: "None (metadata / runbook only)" },
  { id: "alert", label: "Alert" },
  { id: "incident", label: "Incident" },
  { id: "both", label: "Alert and incident" },
  { id: "approval", label: "Propose run for approval" },
];

function toTagOptions(tags: string[]): TagOption[] {
  return tags.map((tag) => ({ value: tag, label: tag }));
}

function normalizeTag(value: string): string {
  return value.trim().toLowerCase();
}

export function AlertCatalogForm({
  initial,
  onSubmit,
  onCancel,
  showWorkflowFields = true,
  submitLabel,
  suggestedTags = [],
}: AlertCatalogFormProps) {
  const { data: workflows } = useWorkflows();
  const { isAIEnabled } = useAISettings();
  const { enhanceDescription, catalog } = useAlertCatalog();
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [runbookUrl, setRunbookUrl] = useState("");
  const [keepWorkflowId, setKeepWorkflowId] = useState("");
  const [autoRunOn, setAutoRunOn] = useState<AlertCatalogAutoRunOn>("none");
  const [disabled, setDisabled] = useState(false);
  const [tags, setTags] = useState<string[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [isEnhancing, setIsEnhancing] = useState(false);

  const tagOptions = useMemo(() => {
    const fromCatalog = (catalog ?? []).flatMap((entry) => entry.tags ?? []);
    const unique = Array.from(
      new Set([...suggestedTags, ...fromCatalog].map(normalizeTag).filter(Boolean))
    ).sort();
    return toTagOptions(unique);
  }, [catalog, suggestedTags]);

  useEffect(() => {
    if (initial) {
      setCode(initial.code);
      setName(initial.name);
      setDescription(initial.description || "");
      setRunbookUrl(initial.runbook_url || "");
      setKeepWorkflowId(initial.keep_workflow_id || "");
      setAutoRunOn(initial.auto_run_on || "none");
      setDisabled(!!initial.disabled);
      setTags((initial.tags ?? []).map(normalizeTag).filter(Boolean));
      return;
    }
    setCode("");
    setName("");
    setDescription("");
    setRunbookUrl("");
    setKeepWorkflowId("");
    setAutoRunOn("none");
    setDisabled(false);
    setTags([]);
  }, [initial]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSaving(true);
    try {
      await onSubmit({
        code,
        name,
        description: description || undefined,
        runbook_url: runbookUrl || undefined,
        keep_workflow_id: keepWorkflowId || undefined,
        auto_run_on: autoRunOn,
        disabled,
        tags,
      });
    } finally {
      setIsSaving(false);
    }
  };

  const canEnhance = Boolean(
    code.trim() || name.trim() || description.trim()
  );

  const handleEnhanceDescription = async () => {
    if (!isAIEnabled) {
      showErrorToast(
        new Error("AI is not configured"),
        "Add an API key under Settings → AI"
      );
      return;
    }
    if (!canEnhance) {
      showErrorToast(
        new Error("Nothing to enhance"),
        "Enter a code, name, or draft description first"
      );
      return;
    }
    setIsEnhancing(true);
    try {
      const result = await enhanceDescription({
        code,
        name,
        description,
        runbook_url: runbookUrl || undefined,
        keep_workflow_id: keepWorkflowId || undefined,
      });
      if (!result?.description) {
        throw new Error("AI returned an empty description");
      }
      setDescription(result.description);
      showSuccessToast("Description enhanced");
    } catch (err) {
      showErrorToast(err, "Failed to enhance description");
    } finally {
      setIsEnhancing(false);
    }
  };

  const handleTagsChange = (selected: MultiValue<TagOption>) => {
    setTags(
      Array.from(
        new Set(
          (selected ?? [])
            .map((option) => normalizeTag(option.value))
            .filter(Boolean)
        )
      )
    );
  };

  const handleCreateTag = (inputValue: string) => {
    const tag = normalizeTag(inputValue);
    if (!tag) {
      return;
    }
    setTags((current) =>
      current.includes(tag) ? current : [...current, tag]
    );
  };

  return (
    <form className="flex flex-col gap-3" onSubmit={handleSubmit}>
      <div>
        <Text>Code</Text>
        <TextInput
          required
          value={code}
          onValueChange={setCode}
          placeholder="DCGM_FI_DEV_GPU_TEMP"
          disabled={!!initial}
        />
        <Text className="text-xs mt-1">
          Reserved label <code>labels.code</code>. Stored as UPPER_SNAKE.
        </Text>
      </div>
      <div>
        <Text>Name</Text>
        <TextInput
          required
          value={name}
          onValueChange={setName}
          placeholder="DCGM GPU temperature"
        />
      </div>
      <div>
        <div className="flex items-center justify-between gap-2">
          <Text>Description</Text>
          <Button
            type="button"
            variant="secondary"
            size="xs"
            icon={TbSparkles}
            loading={isEnhancing}
            disabled={isEnhancing || !canEnhance || !isAIEnabled}
            tooltip={
              isAIEnabled
                ? "Enhance with Settings → AI"
                : "Configure an API key under Settings → AI"
            }
            onClick={handleEnhanceDescription}
          >
            AI
          </Button>
        </div>
        <Textarea
          className="mt-1"
          value={description}
          onValueChange={setDescription}
          placeholder="When this code fires, reset the GPU and page on-call."
        />
      </div>
      <div>
        <Text>Tags</Text>
        <div className="mt-1">
          <CreatableMultiSelect
            value={toTagOptions(tags)}
            onChange={handleTagsChange}
            onCreateOption={handleCreateTag}
            options={tagOptions}
            placeholder="Select or create tags (e.g. nvidia, thermal)"
          />
        </div>
        <Text className="text-xs mt-1">
          Group codes in the catalog (multi-tag). Example:{" "}
          <code>nvidia</code>, <code>dcgm</code>, <code>thermal</code>.
        </Text>
      </div>
      <div>
        <Text>Runbook URL</Text>
        <TextInput
          value={runbookUrl}
          onValueChange={setRunbookUrl}
          placeholder="https://docs.nvidia.com/datacenter/dcgm/latest/reference/dcgm-exporter-metrics.html"
        />
        <Text className="text-xs mt-1">
          Copied onto matching alerts as <code>playbook_url</code>.
        </Text>
      </div>
      {showWorkflowFields && (
        <>
          <div>
            <Text>Keep workflow</Text>
            <Select
              value={keepWorkflowId || "__none__"}
              onValueChange={(value) =>
                setKeepWorkflowId(value === "__none__" ? "" : value)
              }
              placeholder="Optional — auto-run this workflow"
            >
              <SelectItem value="__none__">None</SelectItem>
              {(workflows ?? []).map((workflow) => (
                <SelectItem key={workflow.id} value={workflow.id}>
                  {workflow.name || workflow.id}
                </SelectItem>
              ))}
            </Select>
          </div>
          <div>
            <Text>Auto-run on</Text>
            <Select
              value={autoRunOn}
              onValueChange={(value) =>
                setAutoRunOn((value as AlertCatalogAutoRunOn) || "none")
              }
            >
              {AUTO_RUN_OPTIONS.map((option) => (
                <SelectItem key={option.id} value={option.id}>
                  {option.label}
                </SelectItem>
              ))}
            </Select>
          </div>
        </>
      )}
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={disabled}
          onChange={(event) => setDisabled(event.target.checked)}
        />
        Disabled
      </label>
      <div className="flex gap-2 justify-end mt-2">
        <Button variant="secondary" type="button" onClick={onCancel}>
          Cancel
        </Button>
        <Button color="orange" type="submit" loading={isSaving}>
          {submitLabel || (initial ? "Save" : "Register code")}
        </Button>
      </div>
    </form>
  );
}
