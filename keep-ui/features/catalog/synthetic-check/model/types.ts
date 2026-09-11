export type SyntheticProber = "http" | "tcp" | "dns";

export type SyntheticCheck = {
  id: number;
  check_key: string;
  name: string;
  description?: string | null;
  prober: SyntheticProber | string;
  module_config?: Record<string, unknown> | null;
  targets: string[];
  interval_seconds: number;
  labels?: Record<string, string> | null;
  task_queue: string;
  temporal_provider_id: string;
  provider_name?: string | null;
  schedule_id?: string | null;
  last_results?: Record<string, unknown> | null;
  enabled?: boolean;
  created_by?: string | null;
  created_at?: string;
  updated_by?: string | null;
  updated_at?: string;
};

export type SyntheticCheckInput = {
  check_key?: string;
  name: string;
  description?: string;
  prober: SyntheticProber | string;
  module_config?: Record<string, unknown>;
  targets: string[];
  interval_seconds: number;
  labels?: Record<string, string>;
  task_queue?: string;
  temporal_provider_id: string;
  enabled?: boolean;
};

export type SyntheticCheckRunResult = {
  workflow_id: string;
  run_id?: string;
  task_queue: string;
  workflow_type: string;
  namespace?: string;
  check_id: number;
  check_key: string;
};
