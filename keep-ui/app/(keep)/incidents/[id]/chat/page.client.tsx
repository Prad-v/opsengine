"use client";

import { IncidentChat } from "./incident-chat";
import { IncidentDto } from "@/entities/incidents/model";
import { CopilotKit } from "@copilotkit/react-core";
import { useAISettings } from "@/features/settings/ai";

export function IncidentChatClientPage({
  incident,
  mutateIncident,
}: {
  incident: IncidentDto;
  mutateIncident: () => void;
}) {
  const { isAIEnabled, isLoading } = useAISettings();

  if (isLoading || !isAIEnabled) {
    return null;
  }

  return (
    <CopilotKit showDevConsole={false} runtimeUrl="/api/copilotkit">
      <IncidentChat incident={incident} mutateIncident={mutateIncident} />
    </CopilotKit>
  );
}
