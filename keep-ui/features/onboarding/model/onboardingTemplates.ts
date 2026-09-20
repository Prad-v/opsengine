import type { AlertCodePack } from "./types";

export const ALERT_CODE_PACKS: AlertCodePack[] = [
  {
    id: "payments",
    title: "Payments (HIGH_CPU / HIGH_MEMORY)",
    description: "Matches the Grafana mock payments correlation demo.",
    entries: [
      {
        code: "HIGH_CPU",
        name: "High CPU",
        description: "Host or service CPU is above the warning threshold.",
      },
      {
        code: "HIGH_MEMORY",
        name: "High memory",
        description: "Host or service memory is above the warning threshold.",
      },
    ],
  },
  {
    id: "nvidia-gpu",
    title: "NVIDIA GPU (thermal / memory)",
    description: "Reserved DCGM-style codes used by the GPU remediate demo.",
    entries: [
      {
        code: "NVIDIA_GPU_THERMAL",
        name: "NVIDIA GPU thermal",
        description: "DCGM GPU temperature exceeded threshold.",
      },
      {
        code: "NVIDIA_GPU_MEMORY",
        name: "NVIDIA GPU memory",
        description: "GPU framebuffer utilization near capacity.",
      },
    ],
  },
];

export function slugifyAlertCode(code: string): string {
  return code
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

export function buildCorrelationPayload(code: string) {
  const normalized = slugifyAlertCode(code);
  return {
    ruleName: `Correlate ${normalized}`,
    groupDescription: `Groups alerts whose reserved labels.code is ${normalized}.`,
    celQuery: `has(labels.code) && labels.code == "${normalized}"`,
    sqlQuery: {
      sql: "((labels.code = :code_1))",
      params: { code_1: normalized },
    },
    timeframeInSeconds: 86400,
    timeUnit: "hours",
    groupingCriteria: ["labels.host"],
    requireApprove: false,
    resolveOn: "never",
    createOn: "any",
    threshold: 1,
    incidentNameTemplate: `{{ alert.labels.code }} on {{ alert.labels.host }}`,
    incidentPrefix: "INC",
    multiLevel: false,
    multiLevelPropertyName: "",
    assignee: undefined,
  };
}

export function buildNotifyWorkflowYaml(options: {
  code: string;
  providerType: string;
  providerName?: string;
  workflowId?: string;
}): string {
  const code = slugifyAlertCode(options.code);
  const workflowId =
    options.workflowId || `onboarding-notify-${code.toLowerCase()}`;
  const configLine =
    options.providerType !== "console" && options.providerName
      ? `\n        config: "{{ providers.${options.providerName} }}"`
      : "";

  return `workflow:
  id: ${workflowId}
  name: Notify on ${code}
  description: Created by the setup wizard for reserved alert code ${code}.
  triggers:
    - type: alert
      cel: has(labels.code) && labels.code == "${code}" && status == "firing"
    - type: incident
      events:
        - created
      cel: code == "${code}"
  actions:
    - name: notify-oncall
      provider:
        type: ${options.providerType}${configLine}
        with:
          message: "{{ alert.labels.code or incident.code }} — {{ alert.name or incident.name }}"
`;
}

export function replaceNotifyProvider(
  yaml: string,
  providerType: string,
  providerName?: string
): string {
  const configLine =
    providerType !== "console" && providerName
      ? `\n        config: "{{ providers.${providerName} }}"`
      : "";
  return yaml.replace(
    /provider:\n\s+type:\s*[^\n]+(\n\s+config:\s*"[^"]+")?/,
    `provider:\n        type: ${providerType}${configLine}`
  );
}
