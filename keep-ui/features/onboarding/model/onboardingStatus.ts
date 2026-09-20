import {
  ONBOARDING_STEPS,
  type ComputeOnboardingStatusInput,
  type OnboardingProviderSnapshot,
  type OnboardingStatus,
  type OnboardingWorkflowSnapshot,
} from "./types";

const NOTIFY_PROVIDER_TYPES = [
  "slack",
  "teams",
  "console",
  "resend",
  "smtp",
  "email",
  "ntfy",
  "telegram",
  "discord",
  "pagerduty",
  "opsgenie",
  "google_chat",
  "mattermost",
];

export function isAlertSourceProvider(
  provider: OnboardingProviderSnapshot
): boolean {
  const tags = provider.tags ?? [];
  return (
    tags.includes("alert") ||
    !!provider.can_setup_webhook ||
    !!provider.supports_webhook
  );
}

export function isNotifyProvider(
  provider: OnboardingProviderSnapshot
): boolean {
  const tags = provider.tags ?? [];
  return !!provider.can_notify || tags.includes("messaging");
}

export function workflowHasNotifyAction(
  workflow: OnboardingWorkflowSnapshot
): boolean {
  const raw = workflow.workflow_raw || "";
  if (
    workflow.providers?.some((provider) =>
      NOTIFY_PROVIDER_TYPES.includes(provider.type || "")
    )
  ) {
    return true;
  }
  return NOTIFY_PROVIDER_TYPES.some(
    (type) =>
      raw.includes(`type: ${type}`) || raw.includes(`type: "${type}"`)
  );
}

export function computeOnboardingStatus(
  input: ComputeOnboardingStatusInput
): OnboardingStatus {
  const selectedCode = (input.selectedCode || "").trim();
  const hasAlertProvider = input.installedProviders.some(isAlertSourceProvider);
  const catalogEntry = selectedCode
    ? input.catalog.find((entry) => entry.code === selectedCode)
    : undefined;
  const hasCatalog = !!catalogEntry;
  const hasCorrelation = Boolean(
    (input.ruleId &&
      input.rules.some((rule) => rule.id === input.ruleId)) ||
      (selectedCode &&
        input.rules.some((rule) =>
          (rule.definition_cel || "").includes(selectedCode)
        ))
  );
  const boundWorkflowId =
    catalogEntry?.keep_workflow_id || input.workflowId || "";
  const runWorkflow = boundWorkflowId
    ? input.workflows.find((workflow) => workflow.id === boundWorkflowId)
    : undefined;
  const hasAttachedWorkflow = Boolean(
    catalogEntry?.keep_workflow_id || input.workflowId
  );
  const hasNotification = Boolean(
    input.installedProviders.some(isNotifyProvider) &&
      runWorkflow &&
      workflowHasNotifyAction(runWorkflow)
  );

  const completeById = {
    providers: hasAlertProvider,
    "alert-codes": hasCatalog,
    correlation: hasCorrelation,
    workflow: hasAttachedWorkflow,
    notification: hasNotification,
  } as const;

  const steps = ONBOARDING_STEPS.map((step) => ({
    ...step,
    complete: completeById[step.id],
  }));
  const completedCount = steps.filter((step) => step.complete).length;
  const firstIncompleteIndex = steps.findIndex((step) => !step.complete);

  return {
    steps,
    completedCount,
    totalCount: steps.length,
    isComplete: completedCount === steps.length,
    hasAlertProvider,
    firstIncompleteIndex:
      firstIncompleteIndex === -1 ? steps.length - 1 : firstIncompleteIndex,
  };
}
