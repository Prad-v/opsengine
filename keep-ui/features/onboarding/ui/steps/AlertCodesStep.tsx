"use client";

import { useState } from "react";
import { Button, Callout, Text } from "@tremor/react";
import { showErrorToast, showSuccessToast } from "@/shared/ui";
import { AlertCatalogForm } from "@/features/catalog/alert-code";
import type { AlertCatalogEntryInput } from "@/features/catalog/alert-code";
import type { AlertCatalogEntry } from "@/features/catalog/alert-code";
import { ALERT_CODE_PACKS } from "../../model/onboardingTemplates";

interface AlertCodesStepProps {
  catalog: AlertCatalogEntry[];
  onRegister: (body: AlertCatalogEntryInput) => Promise<AlertCatalogEntry>;
  onSelectCode: (code: string) => void;
  selectedCode: string;
}

export function AlertCodesStep({
  catalog,
  onRegister,
  onSelectCode,
  selectedCode,
}: AlertCodesStepProps) {
  const [isSavingPack, setIsSavingPack] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(catalog.length === 0);

  const seedPack = async (packId: string) => {
    const pack = ALERT_CODE_PACKS.find((item) => item.id === packId);
    if (!pack) {
      return;
    }
    setIsSavingPack(packId);
    try {
      const existing = new Set(catalog.map((entry) => entry.code));
      let lastCode = selectedCode;
      for (const entry of pack.entries) {
        if (existing.has(entry.code)) {
          lastCode = entry.code;
          continue;
        }
        const created = await onRegister({
          code: entry.code,
          name: entry.name,
          description: entry.description,
          auto_run_on: "none",
        });
        lastCode = created.code;
      }
      onSelectCode(lastCode || pack.entries[0].code);
      showSuccessToast(`${pack.title} registered`);
    } catch (error) {
      showErrorToast(error, "Failed to register alert codes");
    } finally {
      setIsSavingPack(null);
    }
  };

  return (
    <div className="space-y-4">
      <Text>
        Reserved <code>labels.code</code> is the join key for catalog, CEL,
        correlation, and workflows. Seed a pack or register one code.
      </Text>
      <div className="flex flex-wrap gap-2">
        {ALERT_CODE_PACKS.map((pack) => (
          <Button
            key={pack.id}
            color="orange"
            variant="secondary"
            loading={isSavingPack === pack.id}
            onClick={() => seedPack(pack.id)}
          >
            {pack.title}
          </Button>
        ))}
        <Button
          variant="secondary"
          color="gray"
          onClick={() => setShowForm(true)}
        >
          Register a custom code
        </Button>
      </div>
      {catalog.length > 0 && (
        <div className="rounded-lg border border-gray-200 p-3">
          <Text className="font-medium mb-2">Registered codes</Text>
          <div className="flex flex-wrap gap-2">
            {catalog.map((entry) => (
              <Button
                key={entry.id}
                size="xs"
                color={selectedCode === entry.code ? "orange" : "gray"}
                variant={selectedCode === entry.code ? "primary" : "secondary"}
                onClick={() => onSelectCode(entry.code)}
              >
                {entry.code}
              </Button>
            ))}
          </div>
        </div>
      )}
      {showForm && (
        <AlertCatalogForm
          showWorkflowFields={false}
          submitLabel="Register code"
          onCancel={() => setShowForm(false)}
          onSubmit={async (body) => {
            const created = await onRegister(body);
            onSelectCode(created.code);
            setShowForm(false);
            showSuccessToast("Alert code registered");
          }}
        />
      )}
      <Callout title="Source does not send labels.code?" color="gray">
        Add a mapping or extraction rule so Keep copies alertname into{" "}
        <code>code</code>. Open{" "}
        <a className="underline" href="/mapping">
          Mapping
        </a>{" "}
        after this wizard if you cannot change the source.
      </Callout>
    </div>
  );
}
