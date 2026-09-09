export type TemporalCatalogEntry = {
  id: string;
  name: string;
  description?: string;
  workflow_type: string;
  task_queue: string;
  workflow_id_template?: string;
  input_mapping?: Record<string, string>;
  provider_id: string;
  provider_name: string;
};

export type TemporalCatalogStartResult = {
  workflow_id: string;
  run_id?: string;
  task_queue: string;
  workflow_type: string;
  namespace?: string;
  catalog_id: string;
  catalog_name?: string;
  incident_id?: string;
  input?: Record<string, unknown>;
};
