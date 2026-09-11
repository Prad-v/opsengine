import { ReactNode } from "react";
import { getIncidentWithErrorHandling } from "./getIncidentWithErrorHandling";
import { IncidentHeaderSkeleton } from "./incident-header-skeleton";
import { IncidentLayoutClient } from "./incident-layout-client";
import { createServerApiClient } from "@/shared/api/server/createServerApiClient";

async function resolveAIEnabled(): Promise<boolean> {
  if (process.env.OPEN_AI_API_KEY || process.env.OPENAI_API_KEY) {
    return true;
  }
  try {
    const api = await createServerApiClient();
    const settings = await api.get<{ api_key_set?: boolean; configured?: boolean }>(
      "/settings/ai"
    );
    return Boolean(settings?.api_key_set || settings?.configured);
  } catch {
    return false;
  }
}

export default async function Layout(
  props: {
    children: ReactNode;
    params: Promise<{ id: string }>;
  }
) {
  const serverParams = await props.params;

  const {
    children
  } = props;

  const AIEnabled = await resolveAIEnabled();
  try {
    const incident = await getIncidentWithErrorHandling(serverParams.id);
    return (
      <IncidentLayoutClient initialIncident={incident} AIEnabled={AIEnabled}>
        {children}
      </IncidentLayoutClient>
    );
  } catch (error) {
    return (
      <div className="flex flex-col gap-4">
        <IncidentHeaderSkeleton />
        {children}
      </div>
    );
  }
}
