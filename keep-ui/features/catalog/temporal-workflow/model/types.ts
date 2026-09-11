export type TemporalCatalogEntry = {
  id: number;
  catalog_key: string;
  name: string;
  description?: string | null;
  workflow_type: string;
  task_queue: string;
  workflow_id_template?: string | null;
  input_mapping?: Record<string, string> | null;
  provider_id: string;
  provider_name?: string | null;
  disabled?: boolean;
  created_by?: string | null;
  created_at?: string;
  updated_by?: string | null;
  updated_at?: string;
};

export type TemporalCatalogEntryInput = {
  catalog_key?: string;
  name: string;
  description?: string;
  workflow_type: string;
  task_queue: string;
  workflow_id_template?: string;
  input_mapping?: Record<string, string>;
  provider_id: string;
  disabled?: boolean;
};

export type TemporalCatalogStartResult = {
  workflow_id: string;
  run_id?: string;
  task_queue: string;
  workflow_type: string;
  namespace?: string;
  catalog_id: string;
  catalog_db_id?: number;
  catalog_name?: string;
  incident_id?: string;
  input?: Record<string, unknown>;
};

export type TemporalLinkedRun = {
  catalog_id?: string;
  catalog_db_id?: number;
  catalog_name?: string;
  workflow_id?: string;
  run_id?: string;
  workflow_type?: string;
  task_queue?: string;
  namespace?: string;
  started_at?: string;
};
