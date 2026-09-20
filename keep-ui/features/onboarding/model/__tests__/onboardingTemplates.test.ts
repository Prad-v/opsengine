import {
  ALERT_CODE_PACKS,
  buildCorrelationPayload,
  buildNotifyWorkflowYaml,
  replaceNotifyProvider,
  slugifyAlertCode,
} from "../onboardingTemplates";

describe("onboardingTemplates", () => {
  it("slugifies reserved codes to UPPER_SNAKE", () => {
    expect(slugifyAlertCode("nvidia gpu thermal")).toBe("NVIDIA_GPU_THERMAL");
    expect(slugifyAlertCode("HIGH_CPU")).toBe("HIGH_CPU");
  });

  it("seeds payments and NVIDIA GPU packs", () => {
    expect(ALERT_CODE_PACKS.map((pack) => pack.id)).toEqual([
      "payments",
      "nvidia-gpu",
    ]);
    expect(ALERT_CODE_PACKS[0].entries.map((entry) => entry.code)).toEqual([
      "HIGH_CPU",
      "HIGH_MEMORY",
    ]);
  });

  it("builds a correlation rule keyed on labels.code", () => {
    const payload = buildCorrelationPayload("high_cpu");
    expect(payload.ruleName).toBe("Correlate HIGH_CPU");
    expect(payload.celQuery).toContain('labels.code == "HIGH_CPU"');
    expect(payload.sqlQuery.params).toEqual({ code_1: "HIGH_CPU" });
    expect(payload.groupingCriteria).toEqual(["labels.host"]);
    expect(payload.incidentNameTemplate).toContain("alert.labels.code");
  });

  it("builds a notify workflow that matches the code on alert and incident", () => {
    const yaml = buildNotifyWorkflowYaml({
      code: "NVIDIA_GPU_THERMAL",
      providerType: "console",
    });
    expect(yaml).toContain("id: onboarding-notify-nvidia_gpu_thermal");
    expect(yaml).toContain(
      'cel: has(labels.code) && labels.code == "NVIDIA_GPU_THERMAL"'
    );
    expect(yaml).toContain('cel: code == "NVIDIA_GPU_THERMAL"');
    expect(yaml).toContain("type: console");
    expect(yaml).not.toContain("config:");
  });

  it("adds a Slack provider config when replacing console", () => {
    const yaml = buildNotifyWorkflowYaml({
      code: "HIGH_CPU",
      providerType: "console",
    });
    const next = replaceNotifyProvider(yaml, "slack", "my-slack");
    expect(next).toContain("type: slack");
    expect(next).toContain('config: "{{ providers.my-slack }}"');
    expect(next).toContain('type: alert');
  });
});
