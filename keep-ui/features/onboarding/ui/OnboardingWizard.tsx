"use client";

import { useRouter } from "next/navigation";
import { Button, Card, Text } from "@tremor/react";
import { PageSubtitle, PageTitle } from "@/shared/ui";
import { useAlertCatalog } from "@/features/catalog/alert-code";
import { useOnboardingProgress } from "../model/useOnboardingProgress";
import { OnboardingStepper } from "./OnboardingStepper";
import { ProvidersStep } from "./steps/ProvidersStep";
import { AlertCodesStep } from "./steps/AlertCodesStep";
import { CorrelationStep } from "./steps/CorrelationStep";
import { WorkflowStep } from "./steps/WorkflowStep";
import { NotificationStep } from "./steps/NotificationStep";

export type OnboardingWizardProps = {
  onClose?: () => void;
  onFinish?: () => void;
};

export function OnboardingWizard({
  onClose,
  onFinish,
}: OnboardingWizardProps = {}) {
  const router = useRouter();
  const {
    draft,
    setDraft,
    status,
    isLoading,
    isLocalhost,
    installedProviders,
    availableProviders,
    catalog,
    workflows,
    startNewLifecycle,
    dismissLanding,
    mutateProviders,
    mutateCatalog,
    mutateRules,
    mutateWorkflows,
  } = useOnboardingProgress();
  const { createEntry, updateEntry } = useAlertCatalog();

  const currentStep = Math.min(
    Math.max(draft.currentStep, 0),
    status.totalCount - 1
  );
  const step = status.steps[currentStep];

  const goToStep = (index: number) => {
    setDraft((current) => ({ ...current, currentStep: index }));
  };

  const selectCode = (code: string) => {
    setDraft((current) => ({
      ...current,
      selectedCode: code,
      ruleId: code === current.selectedCode ? current.ruleId : "",
      workflowId: code === current.selectedCode ? current.workflowId : "",
    }));
  };

  const closeWizard = () => {
    dismissLanding();
    if (onClose) {
      onClose();
      return;
    }
    router.push("/incidents");
  };

  const finishLifecycle = () => {
    dismissLanding();
    if (onFinish) {
      onFinish();
      return;
    }
    router.push("/alerts/feed");
  };

  const openAlertsFeed = () => {
    dismissLanding();
    router.push("/alerts/feed");
  };

  return (
    <div
      className="mx-auto flex max-w-5xl flex-col gap-6 p-4"
      data-testid="onboarding-wizard"
    >
      <header className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
        <div>
          <PageTitle>Onboard an alert lifecycle</PageTitle>
          <PageSubtitle>
            Wire one reserved <code>labels.code</code> from ingest through
            notification. Run the wizard again for the next code — it is not a
            one-time setup.
          </PageSubtitle>
        </div>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            color="orange"
            onClick={startNewLifecycle}
            data-testid="onboard-another"
          >
            Onboard another
          </Button>
          <Button variant="light" color="gray" onClick={closeWizard}>
            Close
          </Button>
        </div>
      </header>

      <Card>
        <OnboardingStepper
          steps={status.steps}
          currentStep={currentStep}
          onSelectStep={goToStep}
        />
        <Text className="mt-3 text-sm text-gray-600">
          {isLoading
            ? "Checking your workspace…"
            : draft.selectedCode
              ? `${draft.selectedCode}: ${status.completedCount} of ${status.totalCount} steps for this lifecycle`
              : `${status.completedCount} of ${status.totalCount} steps — register a code to start this lifecycle`}
        </Text>
      </Card>

      {status.isComplete && draft.selectedCode && (
        <Card className="border-emerald-200 bg-emerald-50 space-y-3">
          <Text className="font-medium text-emerald-900">
            {draft.selectedCode} is wired: ingest → catalog → correlation →
            workflow → notify.
          </Text>
          <div className="flex flex-wrap gap-2">
            {onFinish ? (
              <Button color="orange" onClick={finishLifecycle}>
                Back to list
              </Button>
            ) : null}
            <Button
              color="orange"
              variant={onFinish ? "secondary" : "primary"}
              onClick={openAlertsFeed}
            >
              Open Alerts Feed
            </Button>
            <Button
              variant="secondary"
              color="orange"
              onClick={startNewLifecycle}
            >
              Onboard another code
            </Button>
          </div>
        </Card>
      )}

      <Card className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">{step.title}</h2>
          <Text className="mt-1">{step.description}</Text>
        </div>

        {step.id === "providers" && (
          <ProvidersStep
            availableProviders={availableProviders}
            installedProviders={installedProviders}
            isLocalhost={isLocalhost}
            onInstalled={() => {
              void mutateProviders();
            }}
          />
        )}
        {step.id === "alert-codes" && (
          <AlertCodesStep
            catalog={catalog}
            selectedCode={draft.selectedCode}
            onSelectCode={selectCode}
            onRegister={createEntry}
          />
        )}
        {step.id === "correlation" && (
          <CorrelationStep
            selectedCode={draft.selectedCode}
            hasRule={status.steps[2].complete}
            onCreated={async (ruleId) => {
              if (ruleId) {
                setDraft((current) => ({ ...current, ruleId }));
              }
              await mutateRules();
            }}
          />
        )}
        {step.id === "workflow" && (
          <WorkflowStep
            selectedCode={draft.selectedCode}
            catalog={catalog}
            workflows={workflows}
            workflowId={draft.workflowId}
            onSelectCode={selectCode}
            onWorkflowCreated={(workflowId) => {
              setDraft((current) => ({ ...current, workflowId }));
              void mutateWorkflows();
            }}
            onAttach={async (entry, workflowId, autoRunOn) => {
              await updateEntry(entry.id, {
                code: entry.code,
                name: entry.name,
                description: entry.description || undefined,
                runbook_url: entry.runbook_url || undefined,
                keep_workflow_id: workflowId,
                auto_run_on: autoRunOn,
                disabled: entry.disabled,
              });
              await mutateCatalog();
            }}
          />
        )}
        {step.id === "notification" && (
          <NotificationStep
            availableProviders={availableProviders}
            installedProviders={installedProviders}
            isLocalhost={isLocalhost}
            selectedCode={draft.selectedCode}
            workflowId={draft.workflowId}
            workflows={workflows}
            onInstalled={() => {
              void mutateProviders();
            }}
            onWorkflowUpdated={() => mutateWorkflows()}
          />
        )}

        <div className="flex flex-wrap justify-between gap-2 border-t border-gray-100 pt-4">
          <Button
            variant="secondary"
            color="gray"
            disabled={currentStep === 0}
            onClick={() => goToStep(currentStep - 1)}
          >
            Back
          </Button>
          <div className="flex gap-2">
            {currentStep < status.totalCount - 1 ? (
              <>
                <Button
                  variant="secondary"
                  color="gray"
                  onClick={() => goToStep(currentStep + 1)}
                >
                  Skip this step
                </Button>
                <Button color="orange" onClick={() => goToStep(currentStep + 1)}>
                  Continue
                </Button>
              </>
            ) : (
              <>
                <Button
                  variant="secondary"
                  color="orange"
                  onClick={startNewLifecycle}
                >
                  Onboard another
                </Button>
                <Button color="orange" onClick={finishLifecycle}>
                  {onFinish ? "Finish" : "Finish and open Alerts Feed"}
                </Button>
              </>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
}
