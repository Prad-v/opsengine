export const AI_SETTINGS_SWR_KEY = "/settings/ai";

export interface AISettingsResponse {
  configured: boolean;
  api_key_set: boolean;
  model?: string | null;
  base_url?: string | null;
  organization_id?: string | null;
  source?: string | null;
  env_override?: boolean;
}

export interface UseAISettingsValue {
  settings: AISettingsResponse | undefined;
  isLoading: boolean;
  isAIEnabled: boolean;
  error: Error | undefined;
  mutate: () => Promise<AISettingsResponse | undefined>;
}
