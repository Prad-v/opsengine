"use client";

import React from "react";
import useSWR from "swr";
import {
  Card,
  Title,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  Callout,
} from "@tremor/react";
import Loading from "@/app/(keep)/loading";
import { useApi } from "@/shared/lib/hooks/useApi";
import { useConfig } from "utils/hooks/useConfig";
import { AuthType } from "@/utils/authenticationType";
import { OktaSettingsForm } from "./okta-settings";

interface SSOProvider {
  id: string;
  name: string;
  connected: boolean;
}

interface SSOSettingsProps {
  selected?: boolean;
}

const SSOSettings = ({ selected = true }: SSOSettingsProps) => {
  const api = useApi();
  const { data: config } = useConfig();
  const authType = config?.AUTH_TYPE as AuthType | undefined;

  const { data, error } = useSWR<{
    sso: boolean;
    providers: SSOProvider[] | string[];
    wizardUrl: string;
  }>(
    api.isReady() && selected ? `/settings/sso` : null,
    (url: string) => api.get(url),
    { revalidateOnFocus: false }
  );

  // Okta configuration is available for DB/Okta (and while configuring before switching)
  const showOktaForm =
    authType === AuthType.DB ||
    authType === AuthType.OKTA ||
    authType === AuthType.ONELOGIN ||
    authType === AuthType.KEYCLOAK ||
    authType === AuthType.NOAUTH;

  if (selected && !data && !error && authType === AuthType.KEYCLOAK) {
    return <Loading />;
  }

  const supportsSSO = data?.sso;
  const wizardUrl = data?.wizardUrl;
  const normalizedProviders = (data?.providers || []).map((provider) =>
    typeof provider === "string"
      ? { id: provider, name: provider, connected: true }
      : provider
  );

  return (
    <div className="h-full flex flex-col gap-6 overflow-auto">
      <div>
        <Title>SSO</Title>
        <p className="text-sm text-gray-600 mt-1">
          Configure single sign-on providers. Okta credentials are stored
          securely and used by the backend for token verification.
        </p>
      </div>

      {authType === AuthType.DB && (
        <Callout title="Database auth active" color="teal">
          You are signed in with local DB users. Configure Okta below, then set{" "}
          <code>AUTH_TYPE=OKTA</code> on frontend and backend (with matching{" "}
          <code>OKTA_*</code> env vars on the frontend) to switch sign-in to
          Okta.
        </Callout>
      )}

      {showOktaForm && <OktaSettingsForm selected={selected} />}

      {supportsSSO && normalizedProviders.length > 0 && (
        <Card className="p-4">
          <Title className="mb-2">Connected providers</Title>
          <Table>
            <TableHead>
              <TableRow>
                <TableHeaderCell>Provider</TableHeaderCell>
                <TableHeaderCell>Status</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {normalizedProviders.map((provider) => (
                <TableRow key={provider.id}>
                  <TableCell className="capitalize">{provider.name}</TableCell>
                  <TableCell>
                    {provider.connected ? "Connected" : "Not connected"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      {wizardUrl && (
        <Card className="p-4 flex-grow flex flex-col min-h-[320px]">
          <iframe src={wizardUrl} className="w-full flex-grow border-none" />
        </Card>
      )}

      {error && authType === AuthType.KEYCLOAK && (
        <Callout title="Error" color="rose">
          Failed to load SSO status: {error.message}
        </Callout>
      )}
    </div>
  );
};

export default SSOSettings;
