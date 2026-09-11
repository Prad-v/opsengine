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
  SyntheticCheck,
  SyntheticCheckInput,
  SyntheticProber,
} from "../model/types";

interface SyntheticCheckFormProps {
  initial?: SyntheticCheck | null;
  onSubmit: (body: SyntheticCheckInput) => Promise<void>;
  onCancel: () => void;
}

const DEFAULT_MODULE_CONFIG: Record<SyntheticProber, string> = {
  http: `{
  "method": "GET",
  "timeout_seconds": 5,
  "valid_status_codes": [200]
}`,
  tcp: `{
  "timeout_seconds": 3,
  "port": 443
}`,
  dns: `{
  "timeout_seconds": 3,
  "query_type": "A"
}`,
};

export function SyntheticCheckForm({
  initial,
  onSubmit,
  onCancel,
}: SyntheticCheckFormProps) {
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
  const [prober, setProber] = useState<SyntheticProber>("http");
  const [targetsText, setTargetsText] = useState("");
  const [intervalSeconds, setIntervalSeconds] = useState("60");
  const [moduleConfigText, setModuleConfigText] = useState(
    DEFAULT_MODULE_CONFIG.http
  );
  const [labelsText, setLabelsText] = useState("{}");
  const [taskQueue, setTaskQueue] = useState("keep-synth");
  const [providerId, setProviderId] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (initial) {
      setName(initial.name);
      setDescription(initial.description || "");
      setProber((initial.prober as SyntheticProber) || "http");
      setTargetsText((initial.targets || []).join("\n"));
      setIntervalSeconds(String(initial.interval_seconds || 60));
      setModuleConfigText(
        JSON.stringify(initial.module_config || {}, null, 2)
      );
      setLabelsText(JSON.stringify(initial.labels || {}, null, 2));
      setTaskQueue(initial.task_queue || "keep-synth");
      setProviderId(initial.temporal_provider_id);
      setEnabled(initial.enabled !== false);
      return;
    }
    setName("");
    setDescription("");
    setProber("http");
    setTargetsText("");
    setIntervalSeconds("60");
    setModuleConfigText(DEFAULT_MODULE_CONFIG.http);
    setLabelsText("{}");
    setTaskQueue("keep-synth");
    setProviderId(temporalProviders[0]?.id || "");
    setEnabled(true);
  }, [initial, temporalProviders]);

  const handleProberChange = (value: string) => {
    const next = value as SyntheticProber;
    setProber(next);
    if (!initial) {
      setModuleConfigText(DEFAULT_MODULE_CONFIG[next]);
    }
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    let moduleConfig: Record<string, unknown> = {};
    let labels: Record<string, string> = {};
    try {
      const parsed = JSON.parse(moduleConfigText || "{}");
      if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("module_config must be a JSON object");
      }
      moduleConfig = parsed;
    } catch (err) {
      showErrorToast(err, "Invalid module_config JSON");
      return;
    }
    try {
      const parsed = JSON.parse(labelsText || "{}");
      if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("labels must be a JSON object");
      }
      labels = Object.fromEntries(
        Object.entries(parsed).map(([key, value]) => [key, String(value)])
      );
    } catch (err) {
      showErrorToast(err, "Invalid labels JSON");
      return;
    }

    const targets = targetsText
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    if (targets.length === 0) {
      showErrorToast(new Error("Add at least one target"), "Targets required");
      return;
    }
    if (!providerId) {
      showErrorToast(new Error("Select a Temporal provider"), "Provider required");
      return;
    }

    const interval = Number(intervalSeconds);
    if (!Number.isFinite(interval) || interval < 10) {
      showErrorToast(
        new Error("Interval must be at least 10 seconds"),
        "Invalid interval"
      );
      return;
    }

    setIsSaving(true);
    try {
      await onSubmit({
        check_key: initial?.check_key,
        name: name.trim(),
        description: description.trim() || undefined,
        prober,
        module_config: moduleConfig,
        targets,
        interval_seconds: interval,
        labels,
        task_queue: taskQueue.trim() || "keep-synth",
        temporal_provider_id: providerId,
        enabled,
      });
    } finally {
      setIsSaving(false);
    }
  };

  if (temporalProviders.length === 0) {
    return (
      <Text>
        Install a Temporal provider under Providers before creating synthetic
        checks.
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
          placeholder="Public API health"
        />
        {initial?.check_key ? (
          <Text className="mt-1 text-xs text-tremor-content">
            Check key: <code>{initial.check_key}</code>
          </Text>
        ) : null}
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
        <Text className="mb-1">Prober</Text>
        <Select value={prober} onValueChange={handleProberChange}>
          <SelectItem value="http">http</SelectItem>
          <SelectItem value="tcp">tcp</SelectItem>
          <SelectItem value="dns">dns</SelectItem>
        </Select>
      </div>
      <div>
        <Text className="mb-1">Targets (one per line)</Text>
        <Textarea
          rows={5}
          required
          value={targetsText}
          onChange={(e) => setTargetsText(e.target.value)}
          placeholder={
            prober === "http"
              ? "https://example.com/health"
              : prober === "tcp"
                ? "example.com:443"
                : "example.com"
          }
        />
      </div>
      <div>
        <Text className="mb-1">Interval (seconds)</Text>
        <TextInput
          required
          value={intervalSeconds}
          onChange={(e) => setIntervalSeconds(e.target.value)}
          placeholder="60"
        />
      </div>
      <div>
        <Text className="mb-1">Module config (JSON)</Text>
        <Textarea
          rows={7}
          value={moduleConfigText}
          onChange={(e) => setModuleConfigText(e.target.value)}
        />
      </div>
      <div>
        <Text className="mb-1">Labels (JSON)</Text>
        <Textarea
          rows={3}
          value={labelsText}
          onChange={(e) => setLabelsText(e.target.value)}
        />
      </div>
      <div>
        <Text className="mb-1">Task queue</Text>
        <TextInput
          value={taskQueue}
          onChange={(e) => setTaskQueue(e.target.value)}
          placeholder="keep-synth"
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
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => setEnabled(e.target.checked)}
        />
        Enabled (Temporal Schedule active)
      </label>
      <div className="flex gap-2 justify-end mt-2">
        <Button type="button" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" color="orange" loading={isSaving}>
          {initial ? "Save" : "Create"}
        </Button>
      </div>
    </form>
  );
}
