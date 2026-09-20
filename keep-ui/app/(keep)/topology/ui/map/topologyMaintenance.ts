import { MaintenanceRule } from "@/app/(keep)/maintenance/model";
import { ruleLifecycle } from "@/app/(keep)/maintenance/lib/maintenanceRuleUtils";

export const TOPOLOGY_MAINTENANCE_REASONS = [
  { id: "node_down", label: "Node down" },
  { id: "rma", label: "RMA" },
  { id: "firmware", label: "Firmware / driver upgrade" },
  { id: "thermal", label: "Thermal / cooling" },
  { id: "capacity", label: "Planned capacity work" },
  { id: "other", label: "Other" },
] as const;

export type TopologyMaintenanceReasonId =
  (typeof TOPOLOGY_MAINTENANCE_REASONS)[number]["id"];

export const TOPOLOGY_MAINTENANCE_DURATIONS = [
  { id: "1h", label: "1 hour", seconds: 3600 },
  { id: "4h", label: "4 hours", seconds: 4 * 3600 },
  { id: "8h", label: "8 hours", seconds: 8 * 3600 },
  { id: "24h", label: "24 hours", seconds: 24 * 3600 },
] as const;

export function escapeCelString(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

export function maintenanceCelForService(
  service: string,
  category?: string
): string {
  const escaped = escapeCelString(service);
  switch ((category || "").toLowerCase()) {
    case "gpu":
      return `labels.gpu_id == "${escaped}"`;
    case "host":
      return `labels.host == "${escaped}" || service == "${escaped}"`;
    case "rack":
      return `labels.rack == "${escaped}"`;
    case "row":
      return `labels.row == "${escaped}"`;
    case "datacenter":
      return `labels.datacenter == "${escaped}"`;
    case "region":
      return `labels.region == "${escaped}"`;
    case "service":
      return `service == "${escaped}"`;
    default:
      return [
        `service == "${escaped}"`,
        `labels.host == "${escaped}"`,
        `labels.rack == "${escaped}"`,
        `labels.row == "${escaped}"`,
        `labels.datacenter == "${escaped}"`,
        `labels.region == "${escaped}"`,
        `labels.gpu_id == "${escaped}"`,
      ].join(" || ");
  }
}

export function celLiterals(celQuery: string): string[] {
  return [...celQuery.matchAll(/"((?:\\.|[^"\\])*)"/g)].map((match) =>
    match[1].replace(/\\"/g, '"').replace(/\\\\/g, "\\")
  );
}

export function maintenanceRuleCoversService(
  rule: Pick<MaintenanceRule, "cel_query" | "enabled" | "status" | "start_time" | "end_time">,
  service: string,
  now: Date = new Date()
): boolean {
  if (ruleLifecycle(rule, now) !== "active") {
    return false;
  }
  return celLiterals(rule.cel_query).includes(service);
}

export function findActiveMaintenanceRule<
  T extends Pick<
    MaintenanceRule,
    "cel_query" | "enabled" | "status" | "start_time" | "end_time"
  >,
>(
  rules: T[] | undefined,
  service: string,
  now: Date = new Date()
): T | undefined {
  return (rules ?? []).find((rule) =>
    maintenanceRuleCoversService(rule, service, now)
  );
}

export function topologyMaintenanceRuleName(
  displayName: string,
  reasonLabel: string
): string {
  return `Topology: ${displayName} (${reasonLabel})`;
}

export function findPendingNodeMaintenance<
  T extends {
    action_type?: string;
    status?: string;
    resource_id?: string | null;
    context?: Record<string, unknown>;
    payload?: Record<string, unknown>;
  },
>(requests: T[] | undefined, service: string): T | undefined {
  return (requests ?? []).find((request) => {
    if (request.status && request.status !== "pending") {
      return false;
    }
    if (request.action_type && request.action_type !== "node_maintenance") {
      return false;
    }
    if (request.resource_id === service) {
      return true;
    }
    const contextService = request.context?.service;
    const payloadName = request.payload?.name;
    return contextService === service || payloadName === service;
  });
}
