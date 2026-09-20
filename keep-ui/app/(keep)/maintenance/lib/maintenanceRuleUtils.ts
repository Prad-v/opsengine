import type {
  MaintenanceDurationUnit,
  MaintenanceRule,
  MaintenanceRuleStatus,
} from "../model";

export function durationFromSeconds(seconds: number): {
  value: number;
  unit: MaintenanceDurationUnit;
} {
  const safe = Number.isFinite(seconds) ? Math.max(0, seconds) : 0;
  if (safe > 0 && safe % 86400 === 0) {
    return { value: safe / 86400, unit: "days" };
  }
  if (safe > 0 && safe % 3600 === 0) {
    return { value: safe / 3600, unit: "hours" };
  }
  return { value: Math.max(1, Math.round(safe / 60) || 1), unit: "minutes" };
}

export function durationToSeconds(
  value: number,
  unit: MaintenanceDurationUnit | string
): number {
  const amount = Number.isFinite(value) ? Math.max(1, value) : 1;
  switch (unit) {
    case "hours":
      return amount * 60 * 60;
    case "days":
      return amount * 60 * 60 * 24;
    case "minutes":
    default:
      return amount * 60;
  }
}

export function parseMaintenanceDate(value?: Date | string | null): Date | null {
  if (!value) {
    return null;
  }
  const parsed = value instanceof Date ? value : new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function ruleLifecycle(
  rule: Pick<MaintenanceRule, "enabled" | "start_time" | "end_time" | "status">,
  now: Date = new Date()
): MaintenanceRuleStatus {
  if (rule.status) {
    return rule.status;
  }
  if (!rule.enabled) {
    return "disabled";
  }
  const start = parseMaintenanceDate(rule.start_time);
  const end = parseMaintenanceDate(rule.end_time);
  if (start && now < start) {
    return "upcoming";
  }
  if (end && now > end) {
    return "expired";
  }
  return "active";
}

export function remainingLabel(
  end?: Date | string | null,
  now: Date = new Date()
): string | null {
  const endDate = parseMaintenanceDate(end);
  if (!endDate) {
    return null;
  }
  const diffMs = endDate.getTime() - now.getTime();
  if (diffMs <= 0) {
    return "ended";
  }
  const minutes = Math.round(diffMs / 60000);
  if (minutes < 60) {
    return `${minutes}m left`;
  }
  const hours = Math.round(minutes / 60);
  if (hours < 48) {
    return `${hours}h left`;
  }
  return `${Math.round(hours / 24)}d left`;
}

export const CEL_SHORTCUTS = [
  { label: "All alerts", cel: "true" },
  { label: "Source", cel: 'source == "prometheus"' },
  { label: "Service", cel: 'service == "gpu-node-03"' },
  { label: "Alert code", cel: 'code == "GPU_XID_79"' },
] as const;
