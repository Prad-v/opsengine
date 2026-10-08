export type AlertCatalogAutoRunOn =
  | "none"
  | "alert"
  | "incident"
  | "both"
  | "approval";

export type AlertCatalogDomain =
  | "thermal"
  | "power"
  | "memory"
  | "reliability"
  | "compute"
  | "fabric"
  | "pcie"
  | "diagnostics"
  | "software"
  | "workload"
  | "capacity"
  | "security"
  | "infrastructure";

export type AlertCatalogRole =
  | "symptom"
  | "root_cause"
  | "capacity_signal"
  | "informational"
  | "performance";

export const ALERT_CATALOG_DOMAIN_OPTIONS: {
  id: AlertCatalogDomain;
  label: string;
}[] = [
  { id: "thermal", label: "Thermal" },
  { id: "power", label: "Power" },
  { id: "memory", label: "Memory" },
  { id: "reliability", label: "Reliability / ECC" },
  { id: "compute", label: "Compute" },
  { id: "fabric", label: "Fabric / interconnect" },
  { id: "pcie", label: "PCIe / host I/O" },
  { id: "diagnostics", label: "Diagnostics" },
  { id: "software", label: "Software / driver" },
  { id: "workload", label: "Workload / job" },
  { id: "capacity", label: "Capacity / scheduling" },
  { id: "security", label: "Security" },
  { id: "infrastructure", label: "Infrastructure" },
];

export const ALERT_CATALOG_ROLE_OPTIONS: {
  id: AlertCatalogRole;
  label: string;
}[] = [
  { id: "symptom", label: "Symptom" },
  { id: "root_cause", label: "Root cause" },
  { id: "capacity_signal", label: "Capacity signal" },
  { id: "informational", label: "Informational" },
  { id: "performance", label: "Performance" },
];

export type AlertCatalogEntry = {
  id: number;
  code: string;
  name: string;
  description?: string | null;
  runbook_url?: string | null;
  keep_workflow_id?: string | null;
  auto_run_on: AlertCatalogAutoRunOn;
  disabled?: boolean;
  tags?: string[];
  domain?: AlertCatalogDomain | null;
  role?: AlertCatalogRole | null;
  created_by?: string | null;
  created_at?: string;
  updated_by?: string | null;
  updated_at?: string;
};

export type EnhanceAlertCatalogDescriptionInput = {
  code?: string;
  name?: string;
  description?: string;
  runbook_url?: string;
  keep_workflow_id?: string;
};

export type EnhanceAlertCatalogDescriptionResult = {
  description: string;
  model?: string | null;
};

export type AlertCatalogEntryInput = {
  code: string;
  name: string;
  description?: string;
  runbook_url?: string;
  keep_workflow_id?: string;
  auto_run_on: AlertCatalogAutoRunOn;
  disabled?: boolean;
  tags?: string[];
  domain?: AlertCatalogDomain | null;
  role?: AlertCatalogRole | null;
};
