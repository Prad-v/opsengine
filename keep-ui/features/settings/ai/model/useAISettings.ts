"use client";

import useSWR from "swr";
import { useApi } from "@/shared/lib/hooks/useApi";
import { useConfig } from "@/utils/hooks/useConfig";
import {
  AI_SETTINGS_SWR_KEY,
  AISettingsResponse,
  UseAISettingsValue,
} from "./types";

export function useAISettings(): UseAISettingsValue {
  const api = useApi();
  const { data: config } = useConfig();

  const { data, error, isLoading, mutate } = useSWR<AISettingsResponse>(
    api.isReady() ? AI_SETTINGS_SWR_KEY : null,
    (url) => api.get(url),
    { revalidateOnFocus: false }
  );

  const isAIEnabled = Boolean(
    config?.OPEN_AI_API_KEY_SET || data?.api_key_set || data?.configured
  );

  return {
    settings: data,
    isLoading,
    isAIEnabled,
    error,
    mutate: async () => mutate(),
  };
}
