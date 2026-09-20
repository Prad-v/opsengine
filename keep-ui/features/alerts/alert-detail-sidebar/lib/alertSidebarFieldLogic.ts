import { AlertDto } from "@/entities/alerts/model";

export type AlertSidebarFieldName =
  | "service"
  | "source"
  | "code"
  | "description"
  | "message"
  | "fingerprint"
  | "url"
  | "incidents"
  | "timeline"
  | "relatedServices";

export const DEFAULT_ALERT_SIDEBAR_FIELDS: AlertSidebarFieldName[] = [
  "service",
  "source",
  "code",
  "description",
  "message",
  "fingerprint",
  "url",
  "incidents",
  "timeline",
  "relatedServices",
];

export function getAlertCode(alert: AlertDto): string | undefined {
  const value = alert.code || alert.labels?.code;
  return value ? String(value) : undefined;
}

/** Keep reserved `code` on older ALERT_SIDEBAR_FIELDS lists that omitted it. */
export function mergeDefaultSidebarFields(configuredFields: string[]): string[] {
  const fields = configuredFields.length
    ? [...configuredFields]
    : [...DEFAULT_ALERT_SIDEBAR_FIELDS];

  if (fields.includes("code")) {
    return fields;
  }

  const sourceIdx = fields.indexOf("source");
  const insertAt = sourceIdx === -1 ? 0 : sourceIdx + 1;
  fields.splice(insertAt, 0, "code");
  return fields;
}

export function getEnabledFields(
  configuredFields: string[]
): AlertSidebarFieldName[] {
  return configuredFields.filter((field) =>
    DEFAULT_ALERT_SIDEBAR_FIELDS.includes(field as AlertSidebarFieldName)
  ) as AlertSidebarFieldName[];
}

export function getCustomFields(configuredFields: string[]): string[] {
  return configuredFields.filter(
    (field) =>
      !DEFAULT_ALERT_SIDEBAR_FIELDS.includes(field as AlertSidebarFieldName)
  );
}

/**
 * Get a nested value from an object using dot notation path
 * Supports paths like "labels.alertname" or "annotations.description"
 * Also supports array indices like "incident_dto.0.assignee"
 */
export function getNestedValue(obj: any, path: string): any {
  if (!obj || !path) return undefined;

  const keys = path.split(".");
  let value = obj;

  for (const key of keys) {
    if (value === null || value === undefined) {
      return undefined;
    }

    const arrayMatch = key.match(/^(\w+)\[(\d+)\]$/);
    if (arrayMatch) {
      const [, arrayKey, index] = arrayMatch;
      value = value[arrayKey]?.[parseInt(index, 10)];
    } else {
      value = value[key];
    }
  }

  return value;
}

/**
 * Format a field name for display (convert snake_case or camelCase to Title Case)
 */
export function formatFieldName(fieldPath: string): string {
  const parts = fieldPath.split(".");
  const lastPart = parts[parts.length - 1];

  return lastPart
    .replace(/([A-Z])/g, " $1")
    .replace(/_/g, " ")
    .replace(/^\w/, (c) => c.toUpperCase())
    .trim();
}
