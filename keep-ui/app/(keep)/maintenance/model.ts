export type MaintenanceRuleStatus =
  | "upcoming"
  | "active"
  | "expired"
  | "disabled";

export type MaintenanceDurationUnit = "minutes" | "hours" | "days";

export interface MaintenanceRule {
  id: number;
  name: string;
  description?: string;
  created_by: string;
  cel_query: string;
  start_time: Date;
  end_time?: Date;
  duration_seconds?: number;
  updated_at?: Date;
  suppress: boolean;
  enabled: boolean;
  ignore_statuses: string[];
  priority?: number;
  status?: MaintenanceRuleStatus;
}

export interface MaintenanceRuleCreate {
  name: string;
  description?: string;
  cel_query: string;
  start_time: string;
  duration_seconds: number;
  suppress: boolean;
  enabled: boolean;
  ignore_statuses: string[];
  priority?: number;
  topology_service_id?: string;
  topology_category?: string;
  topology_reason?: string;
}

export interface MaintenancePreviewSample {
  fingerprint?: string;
  name?: string;
  source?: string | string[];
  status?: string;
}

export interface MaintenancePreviewResult {
  count: number;
  sample: MaintenancePreviewSample[];
}
