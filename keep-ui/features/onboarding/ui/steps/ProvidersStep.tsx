"use client";

import { useMemo, useState } from "react";
import { Button, Callout, Text } from "@tremor/react";
import { defaultProvider, type Provider } from "@/shared/api/providers";
import { Drawer } from "@/shared/ui/Drawer";
import ProviderForm from "@/app/(keep)/providers/provider-form";
import ProviderTile from "@/app/(keep)/providers/provider-tile";
import { isAlertSourceProvider } from "../../model/onboardingStatus";

const SUGGESTED_ALERT_TYPES = [
  "grafana",
  "prometheus",
  "datadog",
  "sentry",
  "newrelic",
  "kibana",
  "zabbix",
];

interface ProvidersStepProps {
  availableProviders: Provider[];
  installedProviders: Provider[];
  isLocalhost: boolean;
  onInstalled: () => void;
}

export function ProvidersStep({
  availableProviders,
  installedProviders,
  isLocalhost,
  onInstalled,
}: ProvidersStepProps) {
  const [selectedProvider, setSelectedProvider] = useState<Provider | null>(
    null
  );
  const installedAlertProviders = installedProviders.filter(
    isAlertSourceProvider
  );

  const suggestedProviders = useMemo(() => {
    const available = availableProviders
      .map((provider) => ({
        ...defaultProvider,
        ...provider,
        id: provider.type,
        installed: provider.installed ?? false,
      }))
      .filter(
        (provider) =>
          isAlertSourceProvider(provider) &&
          !provider.coming_soon &&
          Object.keys(provider.config || {}).length > 0
      );
    const suggested = SUGGESTED_ALERT_TYPES.map((type) =>
      available.find((provider) => provider.type === type)
    ).filter((provider): provider is Provider => !!provider);
    const rest = available.filter(
      (provider) => !SUGGESTED_ALERT_TYPES.includes(provider.type)
    );
    return [...suggested, ...rest].slice(0, 12);
  }, [availableProviders]);

  return (
    <div className="space-y-4">
      <Text>
        Connect Grafana, Prometheus, or another alert source — or reuse one
        already installed. Keep will ingest events over webhook when the tool
        supports it.
      </Text>
      {isLocalhost && (
        <Callout title="Local webhooks" color="orange">
          Keep is on localhost, so remote tools cannot push webhooks. Use the
          provider-mock at{" "}
          <a
            className="underline"
            href="http://localhost:8099"
            target="_blank"
            rel="noreferrer"
          >
            localhost:8099
          </a>{" "}
          to register Grafana, or set KEEP_API_URL to a public endpoint.
        </Callout>
      )}
      {installedAlertProviders.length > 0 && (
        <div>
          <Text className="font-medium mb-2">Installed alert sources</Text>
          <div className="flex flex-wrap gap-3">
            {installedAlertProviders.map((provider) => (
              <ProviderTile
                key={provider.id}
                provider={provider}
                onClick={() => setSelectedProvider(provider)}
              />
            ))}
          </div>
        </div>
      )}
      <div>
        <Text className="font-medium mb-2">Connect a provider</Text>
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
        variant="light"
        color="orange"
        onClick={() => window.open("/providers", "_blank")}
      >
        Browse all providers
      </Button>
      <Drawer
        title={
          selectedProvider
            ? `Connect ${selectedProvider.display_name}`
            : "Connect provider"
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
            onConnectChange={(_connecting, connected) => {
              if (connected) {
                setSelectedProvider(null);
                onInstalled();
              }
            }}
          />
        )}
      </Drawer>
    </div>
  );
}
