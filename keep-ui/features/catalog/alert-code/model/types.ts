export type AlertCatalogAutoRunOn =
  | "none"
  | "alert"
  | "incident"
  | "both"
  | "approval";

export type AlertCatalogEntry = {
  id: number;
  code: string;
  name: string;
  description?: string | null;
  runbook_url?: string | null;
  keep_workflow_id?: string | null;
  auto_run_on: AlertCatalogAutoRunOn;
  disabled?: boolean;
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
};
