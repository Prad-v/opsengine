export const ONBOARDING_STEP_IDS = [
  "providers",
  "alert-codes",
  "correlation",
  "workflow",
  "notification",
] as const;

export type OnboardingStepId = (typeof ONBOARDING_STEP_IDS)[number];

export type OnboardingStepDefinition = {
  id: OnboardingStepId;
  index: number;
  title: string;
  shortTitle: string;
  description: string;
};

export type OnboardingStepState = OnboardingStepDefinition & {
  complete: boolean;
};

export type OnboardingStatus = {
  steps: OnboardingStepState[];
  completedCount: number;
  totalCount: number;
  isComplete: boolean;
  firstIncompleteIndex: number;
  hasAlertProvider: boolean;
};

export type OnboardingDraft = {
  currentStep: number;
  selectedCode: string;
  workflowId: string;
  ruleId: string;
  landingDismissed: boolean;
  skipped?: boolean;
  completed?: boolean;
};

export type OnboardingProviderSnapshot = {
  id?: string;
  type?: string;
  tags?: string[];
  can_notify?: boolean;
  can_setup_webhook?: boolean;
  supports_webhook?: boolean;
  coming_soon?: boolean;
};

export type OnboardingCatalogSnapshot = {
  code: string;
  keep_workflow_id?: string | null;
};

export type OnboardingWorkflowSnapshot = {
  id: string;
  workflow_raw?: string;
  providers?: { type?: string }[];
};

export type OnboardingRuleSnapshot = {
  id?: string;
  definition_cel?: string;
};

export type ComputeOnboardingStatusInput = {
  installedProviders: OnboardingProviderSnapshot[];
  catalog: OnboardingCatalogSnapshot[];
  rules: OnboardingRuleSnapshot[];
  workflows: OnboardingWorkflowSnapshot[];
  selectedCode: string;
  workflowId: string;
  ruleId: string;
};

export type AlertCodePack = {
  id: string;
  title: string;
  description: string;
  entries: {
    code: string;
    name: string;
    description: string;
  }[];
};

export const ONBOARDING_DRAFT_STORAGE_KEY = "onboarding-progress";

export const DEFAULT_ONBOARDING_DRAFT: OnboardingDraft = {
  currentStep: 0,
  selectedCode: "",
  workflowId: "",
  ruleId: "",
  landingDismissed: false,
};

export const ONBOARDING_STEPS: OnboardingStepDefinition[] = [
  {
    id: "providers",
    index: 0,
    title: "Select or configure providers",
    shortTitle: "Providers",
    description:
      "Reuse an installed alert source, or connect Grafana, Prometheus, or another tool. Enable the webhook when the tool supports it.",
  },
  {
    id: "alert-codes",
    index: 1,
    title: "Register this alert code",
    shortTitle: "Alert codes",
    description:
      "The reserved labels.code for this lifecycle. Catalog, CEL, correlation, and workflows all join on this identity.",
  },
  {
    id: "correlation",
    index: 2,
    title: "Correlate this code into an incident",
    shortTitle: "Correlation",
    description:
      "Create a rule that groups alerts with this reserved code (and host or service) into one incident.",
  },
  {
    id: "workflow",
    index: 3,
    title: "Attach a workflow to this code",
    shortTitle: "Workflow",
    description:
      "Create a Keep workflow keyed on this code and auto-run it from the catalog for the alert, the incident, or both.",
  },
  {
    id: "notification",
    index: 4,
    title: "Notify on this lifecycle",
    shortTitle: "Notification",
    description:
      "Reuse Slack, email, or console, or install a notifier, then point this workflow's notify action at it.",
  },
];
