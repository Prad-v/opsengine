"use client";

import { FormEvent, useEffect, useState } from "react";
import { Button, Text, TextInput } from "@tremor/react";
import { showErrorToast, showSuccessToast } from "@/shared/ui";
import { useApi } from "@/shared/lib/hooks/useApi";
import { buildCorrelationPayload } from "../../model/onboardingTemplates";

interface CorrelationStepProps {
  selectedCode: string;
  hasRule: boolean;
  onCreated: (ruleId?: string) => Promise<unknown> | void;
}

export function CorrelationStep({
  selectedCode,
  hasRule,
  onCreated,
}: CorrelationStepProps) {
  const api = useApi();
  const [code, setCode] = useState(selectedCode);
  const [name, setName] = useState("");
  const [cel, setCel] = useState("");
  const [grouping, setGrouping] = useState("labels.host");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    const payload = buildCorrelationPayload(selectedCode || "HIGH_CPU");
    setCode(selectedCode);
    setName(payload.ruleName);
    setCel(payload.celQuery);
  }, [selectedCode]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!code) {
      showErrorToast(
        new Error("Select an alert code first"),
        "Register an alert code in the previous step"
      );
      return;
    }
    setIsSaving(true);
    try {
      const payload = {
        ...buildCorrelationPayload(code),
        ruleName: name || `Correlate ${code}`,
        celQuery: cel,
        groupingCriteria: grouping
          ? grouping.split(",").map((value) => value.trim()).filter(Boolean)
          : [],
      };
      const created = await api.post<{ id?: string }>("/rules", payload);
      showSuccessToast("Correlation rule created");
      await onCreated(created?.id);
    } catch (error) {
      showErrorToast(error, "Failed to create correlation rule");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <form className="space-y-4" onSubmit={handleSubmit}>
      <Text>
        Group alerts that share the reserved code into one incident. Default
        grouping is host so GPU or node storms collapse together.
      </Text>
      {hasRule && (
        <Text className="text-emerald-700">
          A correlation rule already exists for this code. You can create
          another or continue.
        </Text>
      )}
      <div>
        <Text>Alert code</Text>
        <TextInput
          required
          value={code}
          onValueChange={setCode}
          placeholder="NVIDIA_GPU_THERMAL"
        />
      </div>
      <div>
        <Text>Rule name</Text>
        <TextInput required value={name} onValueChange={setName} />
      </div>
      <div>
        <Text>CEL</Text>
        <TextInput required value={cel} onValueChange={setCel} />
      </div>
      <div>
        <Text>Group by</Text>
        <TextInput
          value={grouping}
          onValueChange={setGrouping}
          placeholder="labels.host"
        />
      </div>
      <Button color="orange" type="submit" loading={isSaving}>
        Create correlation
      </Button>
    </form>
  );
}
