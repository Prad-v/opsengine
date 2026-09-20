import type { AlertCatalogEntry } from "@/features/catalog/alert-code";
import { computeOnboardingStatus } from "./onboardingStatus";
import type {
  OnboardingProviderSnapshot,
  OnboardingStatus,
} from "./types";

export type LifecycleWorkflowSnapshot = {
  id: string;
  name?: string;
  workflow_raw?: string;
  workflow_raw_id?: string;
  disabled?: boolean;
  providers?: { type?: string }[];
};

export type LifecycleRuleSnapshot = {
  id?: string;
  name?: string;
  definition_cel?: string;
};

export type LifecycleRow = {
  id: number;
  code: string;
  name: string;
  description?: string | null;
  paused: boolean;
  correlation: { id: string; name: string } | null;
  workflow: { id: string; name: string; disabled?: boolean } | null;
  autoRunOn: AlertCatalogEntry["auto_run_on"];
  notification: boolean;
  completedCount: number;
  totalCount: number;
  isComplete: boolean;
  updatedAt?: string;
  entry: AlertCatalogEntry;
  status: OnboardingStatus;
};

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function ruleMatchesCode(
  cel: string | undefined | null,
  code: string
): boolean {
  const trimmed = (code || "").trim();
  if (!cel || !trimmed) {
    return false;
  }
  return new RegExp(`['"]${escapeRegExp(trimmed)}['"]`).test(cel);
}

export function findWorkflowForCatalog(
  workflows: LifecycleWorkflowSnapshot[],
  keepWorkflowId: string | null | undefined
): LifecycleWorkflowSnapshot | undefined {
  if (!keepWorkflowId) {
    return undefined;
  }
  return workflows.find(
    (workflow) =>
      workflow.id === keepWorkflowId ||
      workflow.workflow_raw_id === keepWorkflowId
  );
}

export function findRuleForCode(
  rules: LifecycleRuleSnapshot[],
  code: string
): LifecycleRuleSnapshot | undefined {
  return rules.find((rule) => ruleMatchesCode(rule.definition_cel, code));
}

export function buildLifecycleRows({
  catalog,
  rules,
  workflows,
  installedProviders,
}: {
  catalog: AlertCatalogEntry[];
  rules: LifecycleRuleSnapshot[];
  workflows: LifecycleWorkflowSnapshot[];
  installedProviders: OnboardingProviderSnapshot[];
}): LifecycleRow[] {
  return catalog.map((entry) => {
    const matchingRule = findRuleForCode(rules, entry.code);
    const matchingWorkflow = findWorkflowForCatalog(
      workflows,
      entry.keep_workflow_id
    );
    const status = computeOnboardingStatus({
      installedProviders,
      catalog,
      rules,
      workflows,
      selectedCode: entry.code,
      workflowId: entry.keep_workflow_id || "",
      ruleId: matchingRule?.id || "",
    });

    return {
      id: entry.id,
      code: entry.code,
      name: entry.name,
      description: entry.description,
      paused: Boolean(entry.disabled),
      correlation: matchingRule?.id
        ? {
            id: matchingRule.id,
            name: matchingRule.name || matchingRule.id,
          }
        : null,
      workflow: matchingWorkflow
        ? {
            id: matchingWorkflow.id,
            name: matchingWorkflow.name || matchingWorkflow.id,
            disabled: matchingWorkflow.disabled,
          }
        : entry.keep_workflow_id
          ? {
              id: entry.keep_workflow_id,
              name: entry.keep_workflow_id,
            }
          : null,
      autoRunOn: entry.auto_run_on,
      notification: Boolean(
        status.steps.find((step) => step.id === "notification")?.complete
      ),
      completedCount: status.completedCount,
      totalCount: status.totalCount,
      isComplete: status.isComplete,
      updatedAt: entry.updated_at || entry.created_at,
      entry,
      status,
    };
  });
}
