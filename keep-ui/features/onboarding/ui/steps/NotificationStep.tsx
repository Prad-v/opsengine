"use client";

import { useMemo, useState } from "react";
import { Button, Callout, Text } from "@tremor/react";
import { defaultProvider, type Provider } from "@/shared/api/providers";
import { Drawer } from "@/shared/ui/Drawer";
import { showErrorToast, showSuccessToast } from "@/shared/ui";
import ProviderForm from "@/app/(keep)/providers/provider-form";
import ProviderTile from "@/app/(keep)/providers/provider-tile";
import { useWorkflowActions } from "@/entities/workflows/model";
import { useApi } from "@/shared/lib/hooks/useApi";
import { isNotifyProvider } from "../../model/onboardingStatus";
import { buildNotifyWorkflowYaml } from "../../model/onboardingTemplates";
import type { OnboardingWorkflowSnapshot } from "../../model/types";

const SUGGESTED_NOTIFY_TYPES = [
  "slack",
  "teams",
  "smtp",
  "resend",
  "console",
  "ntfy",
  "telegram",
];

interface NotificationStepProps {
  availableProviders: Provider[];
  installedProviders: Provider[];
  isLocalhost: boolean;
  selectedCode: string;
  workflowId: string;
  workflows: OnboardingWorkflowSnapshot[];
  onInstalled: () => void;
  onWorkflowUpdated: () => Promise<unknown> | void;
}

export function NotificationStep({
  availableProviders,
  installedProviders,
  isLocalhost,
  selectedCode,
  workflowId,
  workflows,
  onInstalled,
  onWorkflowUpdated,
}: NotificationStepProps) {
  const { createWorkflow, updateWorkflow } = useWorkflowActions();
  const api = useApi();
  const [selectedProvider, setSelectedProvider] = useState<Provider | null>(
    null
  );
  const [isUpdating, setIsUpdating] = useState(false);
  const resolvedWorkflowId =
    workflowId ||
    workflows.find((workflow) =>
      (workflow.id || "").startsWith("onboarding-notify")
    )?.id ||
    "";

  const installedNotifiers = installedProviders.filter(isNotifyProvider);
  const suggestedProviders = useMemo(() => {
    const available = availableProviders
      .map((provider) => ({
        ...defaultProvider,
        ...provider,
        id: provider.type,
        installed: provider.installed ?? false,
      }))
      .filter(
        (provider) => isNotifyProvider(provider) && !provider.coming_soon
      );
    const suggested = SUGGESTED_NOTIFY_TYPES.map((type) =>
      available.find((provider) => provider.type === type)
    ).filter((provider): provider is Provider => !!provider);
    return suggested.length > 0 ? suggested : available.slice(0, 8);
  }, [availableProviders]);

  const applyNotifier = async (providerType: string, providerName?: string) => {
    if (!selectedCode) {
      showErrorToast(
        new Error("Select an alert code first"),
        "Finish the alert code step so the notify workflow has a CEL key"
      );
      return;
    }
    setIsUpdating(true);
    try {
      const yaml = buildNotifyWorkflowYaml({
        code: selectedCode,
        providerType,
        providerName,
        workflowId: resolvedWorkflowId || undefined,
      });
      if (resolvedWorkflowId) {
        const updated = await updateWorkflow(resolvedWorkflowId, yaml);
        if (!updated) {
          throw new Error("Workflow was not updated");
        }
      } else {
        const created = await createWorkflow(yaml);
        if (!created?.workflow_id) {
          throw new Error("Workflow was not created");
        }
      }
      await onWorkflowUpdated();
      showSuccessToast(
        providerType === "console"
          ? "Workflow will log to the console"
          : `Workflow will notify via ${providerType}`
      );
    } catch (error) {
      showErrorToast(error, "Failed to configure notification");
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <div className="space-y-4">
      <Text>
        Notifications are workflow actions. Install Slack, email, or console,
        then point the onboarding workflow at that provider.
      </Text>
      {installedNotifiers.length > 0 && (
        <div>
          <Text className="font-medium mb-2">Installed notifiers</Text>
          <div className="flex flex-wrap gap-3">
            {installedNotifiers.map((provider) => (
              <div key={provider.id} className="space-y-2">
                <ProviderTile
                  provider={provider}
                  onClick={() => setSelectedProvider(provider)}
                />
                <Button
                  size="xs"
                  color="orange"
                  loading={isUpdating}
                  onClick={() =>
                    applyNotifier(
                      provider.type,
                      provider.details?.name || provider.id
                    )
                  }
                >
                  Use {provider.display_name || provider.type}
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}
      <div>
        <Text className="font-medium mb-2">Connect a notifier</Text>
        <div className="flex flex-wrap gap-3">
          {suggestedProviders.map((provider) => (
            <ProviderTile
              key={provider.type}
              provider={provider}
              onClick={() => setSelectedProvider(provider)}
            />
          ))}
        </div>
      </div>
      <Button
        variant="secondary"
        color="orange"
        loading={isUpdating}
        onClick={async () => {
          try {
            await api.post("/providers/install", {
              provider_id: "console",
              provider_name: "onboarding-console",
              provider_type: "console",
            });
            onInstalled();
          } catch {
            // Already installed is fine — still point the workflow at console.
          }
          await applyNotifier("console", "onboarding-console");
        }}
      >
        Use console logs (local / debug)
      </Button>
      {isLocalhost && (
        <Callout title="Local demo" color="gray">
          Console is enough to prove the path. Slack and email still work if
          you install them; webhooks from those tools also need a public Keep
          URL.
        </Callout>
      )}
      <Drawer
        title={
          selectedProvider
            ? `Connect ${selectedProvider.display_name}`
            : "Connect notifier"
        }
        isOpen={!!selectedProvider}
        onClose={() => setSelectedProvider(null)}
      >
        {selectedProvider && (
          <ProviderForm
            provider={selectedProvider}
            closeModal={() => setSelectedProvider(null)}
            installedProvidersMode={!!selectedProvider.installed}
            isProviderNameDisabled={!!selectedProvider.installed}
            isLocalhost={isLocalhost}
            mutate={onInstalled}
            onConnectChange={(_connecting, connected, installed) => {
              if (connected) {
                setSelectedProvider(null);
                onInstalled();
                applyNotifier(
                  selectedProvider.type,
                  installed?.details?.name || selectedProvider.type
                );
              }
            }}
          />
        )}
      </Drawer>
    </div>
  );
}
