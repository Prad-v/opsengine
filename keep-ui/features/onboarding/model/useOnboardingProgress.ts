"use client";

import { useCallback, useMemo } from "react";
import { useProviders } from "@/utils/hooks/useProviders";
import { useRules } from "@/utils/hooks/useRules";
import { useWorkflows } from "@/entities/workflows/model";
import { useAlertCatalog } from "@/features/catalog/alert-code";
import { useLocalStorage } from "@/utils/hooks/useLocalStorage";
import { computeOnboardingStatus } from "./onboardingStatus";
import { findRuleForCode } from "./lifecycleRows";
import {
  DEFAULT_ONBOARDING_DRAFT,
  ONBOARDING_DRAFT_STORAGE_KEY,
  type OnboardingDraft,
} from "./types";

export function useOnboardingProgress() {
  const {
    data: providersData,
    isLoading: isProvidersLoading,
    mutate: mutateProviders,
  } = useProviders({
    revalidateOnFocus: false,
  });
  const { catalog, isLoading: isCatalogLoading, mutate: mutateCatalog } =
    useAlertCatalog();
  const { data: rules, isLoading: isRulesLoading, mutate: mutateRules } =
    useRules({ revalidateOnFocus: false });
  const {
    data: workflows,
    isLoading: isWorkflowsLoading,
    mutate: mutateWorkflows,
  } = useWorkflows({ revalidateOnFocus: false });
  const [draft, setDraft] = useLocalStorage<OnboardingDraft>(
    ONBOARDING_DRAFT_STORAGE_KEY,
    DEFAULT_ONBOARDING_DRAFT
  );

  const installedProviders = providersData?.installed_providers ?? [];
  const availableProviders = providersData?.providers ?? [];
  const status = useMemo(
    () =>
      computeOnboardingStatus({
        installedProviders,
        catalog,
        rules: rules ?? [],
        workflows: workflows ?? [],
        selectedCode: draft.selectedCode || "",
        workflowId: draft.workflowId || "",
        ruleId: draft.ruleId || "",
      }),
    [
      installedProviders,
      catalog,
      rules,
      workflows,
      draft.selectedCode,
      draft.workflowId,
      draft.ruleId,
    ]
  );

  const isLoading =
    isProvidersLoading ||
    isCatalogLoading ||
    isRulesLoading ||
    isWorkflowsLoading;

  const landingDismissed = Boolean(
    draft.landingDismissed || draft.skipped || draft.completed
  );
  const shouldRedirectToWizard =
    !landingDismissed && !status.hasAlertProvider;

  const startNewLifecycle = useCallback(() => {
    setDraft({
      ...DEFAULT_ONBOARDING_DRAFT,
      landingDismissed: true,
      currentStep: status.hasAlertProvider ? 1 : 0,
    });
  }, [setDraft, status.hasAlertProvider]);

  const editLifecycle = useCallback(
    (code: string) => {
      const entry = catalog.find((item) => item.code === code);
      const matchingRule = findRuleForCode(rules ?? [], code);
      const nextStatus = computeOnboardingStatus({
        installedProviders,
        catalog,
        rules: rules ?? [],
        workflows: workflows ?? [],
        selectedCode: code,
        workflowId: entry?.keep_workflow_id || "",
        ruleId: matchingRule?.id || "",
      });
      setDraft({
        ...DEFAULT_ONBOARDING_DRAFT,
        landingDismissed: true,
        selectedCode: code,
        workflowId: entry?.keep_workflow_id || "",
        ruleId: matchingRule?.id || "",
        currentStep: nextStatus.firstIncompleteIndex,
      });
    },
    [catalog, installedProviders, rules, setDraft, workflows]
  );

  const dismissLanding = useCallback(() => {
    setDraft((current) => ({ ...current, landingDismissed: true }));
  }, [setDraft]);

  return {
    draft,
    setDraft,
    status,
    isLoading,
    shouldRedirectToWizard,
    startNewLifecycle,
    editLifecycle,
    dismissLanding,
    isLocalhost: !!providersData?.is_localhost,
    installedProviders,
    availableProviders,
    catalog,
    rules: rules ?? [],
    workflows: workflows ?? [],
    mutateProviders,
    mutateCatalog,
    mutateRules,
    mutateWorkflows,
  };
}
