"use client";

import { CopilotKit } from "@copilotkit/react-core";
import {
  WorkflowBuilderWidget,
  WorkflowBuilderWidgetProps,
} from "./workflow-builder-widget";
import { useAISettings } from "@/features/settings/ai";

export function WorkflowBuilderWidgetSafe(props: WorkflowBuilderWidgetProps) {
  const { isAIEnabled, isLoading } = useAISettings();

  if (isLoading || !isAIEnabled) {
    return <WorkflowBuilderWidget {...props} />;
  }

  return (
    <CopilotKit runtimeUrl="/api/copilotkit" data-testid="copilot-wrapper">
      <WorkflowBuilderWidget {...props} />
    </CopilotKit>
  );
}
