import {
  computeOnboardingStatus,
  isAlertSourceProvider,
  isNotifyProvider,
  workflowHasNotifyAction,
} from "../onboardingStatus";

const emptyRun = {
  selectedCode: "",
  workflowId: "",
  ruleId: "",
};

describe("computeOnboardingStatus", () => {
  it("starts with every step incomplete for a new lifecycle run", () => {
    const status = computeOnboardingStatus({
      installedProviders: [],
      catalog: [],
      rules: [],
      workflows: [],
      ...emptyRun,
    });

    expect(status.completedCount).toBe(0);
    expect(status.isComplete).toBe(false);
    expect(status.firstIncompleteIndex).toBe(0);
    expect(status.hasAlertProvider).toBe(false);
    expect(status.steps.map((step) => step.id)).toEqual([
      "providers",
      "alert-codes",
      "correlation",
      "workflow",
      "notification",
    ]);
  });

  it("reuses an installed alert source without treating catalog as done", () => {
    expect(
      isAlertSourceProvider({ tags: ["alert"], type: "grafana" })
    ).toBe(true);
    expect(isNotifyProvider({ can_notify: true, type: "slack" })).toBe(true);

    const status = computeOnboardingStatus({
      installedProviders: [{ type: "grafana", tags: ["alert"] }],
      catalog: [{ code: "HIGH_CPU", keep_workflow_id: "old-workflow" }],
      rules: [{ id: "rule-1", definition_cel: 'labels.code == "HIGH_CPU"' }],
      workflows: [],
      ...emptyRun,
    });

    expect(status.steps[0].complete).toBe(true);
    expect(status.steps.find((step) => step.id === "alert-codes")?.complete).toBe(
      false
    );
    expect(status.firstIncompleteIndex).toBe(1);
  });

  it("completes only the selected code's lifecycle, not another catalog row", () => {
    const status = computeOnboardingStatus({
      installedProviders: [
        { type: "grafana", tags: ["alert"] },
        { type: "slack", can_notify: true, tags: ["messaging"] },
      ],
      catalog: [
        { code: "HIGH_CPU", keep_workflow_id: "onboarding-notify-high-cpu" },
        { code: "NVIDIA_GPU_THERMAL" },
      ],
      rules: [
        { id: "rule-cpu", definition_cel: 'labels.code == "HIGH_CPU"' },
      ],
      workflows: [
        {
          id: "onboarding-notify-high-cpu",
          workflow_raw:
            'triggers:\n  - type: alert\n    cel: labels.code == "HIGH_CPU"\nactions:\n  - provider:\n      type: slack\n',
        },
      ],
      selectedCode: "NVIDIA_GPU_THERMAL",
      workflowId: "",
      ruleId: "",
    });

    expect(status.steps.find((step) => step.id === "providers")?.complete).toBe(
      true
    );
    expect(
      status.steps.find((step) => step.id === "alert-codes")?.complete
    ).toBe(true);
    expect(
      status.steps.find((step) => step.id === "correlation")?.complete
    ).toBe(false);
    expect(status.steps.find((step) => step.id === "workflow")?.complete).toBe(
      false
    );
    expect(status.isComplete).toBe(false);
  });

  it("requires this code's catalog, rule, attached workflow, and notify", () => {
    const status = computeOnboardingStatus({
      installedProviders: [
        { type: "grafana", tags: ["alert"] },
        { type: "slack", can_notify: true, tags: ["messaging"] },
      ],
      catalog: [
        { code: "HIGH_CPU", keep_workflow_id: "onboarding-notify-high-cpu" },
      ],
      rules: [
        { id: "rule-1", definition_cel: 'labels.code == "HIGH_CPU"' },
      ],
      workflows: [
        {
          id: "onboarding-notify-high-cpu",
          workflow_raw:
            'triggers:\n  - type: alert\n    cel: labels.code == "HIGH_CPU"\nactions:\n  - provider:\n      type: slack\n',
        },
      ],
      selectedCode: "HIGH_CPU",
      workflowId: "onboarding-notify-high-cpu",
      ruleId: "rule-1",
    });

    expect(status.steps.every((step) => step.complete)).toBe(true);
    expect(status.isComplete).toBe(true);
    expect(
      workflowHasNotifyAction({
        id: "w",
        workflow_raw: "provider:\n        type: slack\n",
      })
    ).toBe(true);
  });

  it("does not complete notification when this workflow has no notify action", () => {
    const status = computeOnboardingStatus({
      installedProviders: [{ type: "grafana", tags: ["alert"] }],
      catalog: [{ code: "HIGH_CPU", keep_workflow_id: "wf-1" }],
      rules: [{ id: "r1", definition_cel: 'labels.code == "HIGH_CPU"' }],
      workflows: [
        {
          id: "wf-1",
          workflow_raw: 'cel: labels.code == "HIGH_CPU"',
        },
      ],
      selectedCode: "HIGH_CPU",
      workflowId: "wf-1",
      ruleId: "r1",
    });

    expect(status.steps.find((step) => step.id === "workflow")?.complete).toBe(
      true
    );
    expect(
      status.steps.find((step) => step.id === "notification")?.complete
    ).toBe(false);
  });
});
