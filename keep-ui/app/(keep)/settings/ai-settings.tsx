"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Button,
  Callout,
  TextInput,
  Subtitle,
  Title,
} from "@tremor/react";
import useSWR from "swr";
import Loading from "@/app/(keep)/loading";
import { useApi } from "@/shared/lib/hooks/useApi";
import { KeepApiError } from "@/shared/api";
import { PageSubtitle, Select } from "@/shared/ui";
import {
  AISettingsResponse,
  AI_SETTINGS_SWR_KEY,
} from "@/features/settings/ai/model/types";
import { mutate } from "swr";

interface AISettingsFormState {
  api_key: string;
  model: string;
  base_url: string;
  organization_id: string;
}

interface AISettingsFormProps {
  selectedTab: string;
}

type ModelOption = { value: string; label: string };

export function AISettingsForm({ selectedTab }: AISettingsFormProps) {
  const api = useApi();
  const [settings, setSettings] = useState<AISettingsFormState>({
    api_key: "",
    model: "gpt-4o-mini",
    base_url: "",
    organization_id: "",
  });
  const [configured, setConfigured] = useState(false);
  const [apiKeySet, setApiKeySet] = useState(false);
  const [envOverride, setEnvOverride] = useState(false);
  const [source, setSource] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const [modelOptions, setModelOptions] = useState<ModelOption[]>([]);
  const [shouldFetch, setShouldFetch] = useState(true);

  const shouldFetchUrl =
    api.isReady() && shouldFetch && selectedTab === "ai"
      ? AI_SETTINGS_SWR_KEY
      : null;

  const {
    data,
    error,
    isValidating: isLoading,
  } = useSWR<AISettingsResponse>(shouldFetchUrl, (url) => api.get(url), {
    revalidateOnFocus: false,
  });

  useEffect(() => {
    if (!data) return;
    setConfigured(Boolean(data.configured));
    setApiKeySet(Boolean(data.api_key_set));
    setEnvOverride(Boolean(data.env_override));
    setSource(data.source || null);
    setSettings({
      api_key: "",
      model: data.model || "gpt-4o-mini",
      base_url: data.base_url || "",
      organization_id: data.organization_id || "",
    });
    setShouldFetch(false);
  }, [data]);

  const loadModels = useCallback(async () => {
    if (!api.isReady()) return;
    setIsLoadingModels(true);
    setErrorMessage("");
    try {
      const payload: Record<string, string> = {
        model: settings.model,
        base_url: settings.base_url.trim(),
        organization_id: settings.organization_id.trim(),
      };
      if (settings.api_key) {
        payload.api_key = settings.api_key;
      }
      const response =
        settings.api_key || apiKeySet
          ? await api.post<{ models: string[]; source: string }>(
              "/settings/ai/models",
              payload
            )
          : await api.get<{ models: string[]; source: string }>(
              "/settings/ai/models"
            );
      const options = (response.models || []).map((m) => ({
        value: m,
        label: m,
      }));
      setModelOptions(options);
      if (
        settings.model &&
        options.length > 0 &&
        !options.some((o) => o.value === settings.model)
      ) {
        // keep custom model as selectable option
        setModelOptions([{ value: settings.model, label: settings.model }, ...options]);
      }
    } catch (err) {
      if (err instanceof KeepApiError) {
        setErrorMessage(err.message || "Failed to load models");
      } else {
        setErrorMessage("Failed to load models");
      }
    } finally {
      setIsLoadingModels(false);
    }
  }, [api, apiKeySet, settings.api_key, settings.base_url, settings.model, settings.organization_id]);

  useEffect(() => {
    if (selectedTab === "ai" && api.isReady() && !shouldFetch) {
      void loadModels();
    }
    // Intentionally run when tab becomes active / initial load completes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTab, api.isReady(), shouldFetch]);

  const selectedModelOption = useMemo(() => {
    if (!settings.model) return null;
    return (
      modelOptions.find((o) => o.value === settings.model) || {
        value: settings.model,
        label: settings.model,
      }
    );
  }, [modelOptions, settings.model]);

  if (isLoading && shouldFetch) {
    return <Loading />;
  }

  if (error) {
    return (
      <Callout title="Error" color="rose">
        Failed to load AI settings: {error.message}
      </Callout>
    );
  }

  const onSave = async () => {
    setErrorMessage("");
    setSuccessMessage("");
    setTestResult(null);
    if (!settings.api_key && !apiKeySet) {
      setErrorMessage("API key is required");
      return;
    }
    if (!settings.model.trim()) {
      setErrorMessage("Model is required");
      return;
    }

    setIsSaving(true);
    try {
      const payload: Record<string, string> = {
        model: settings.model.trim(),
        base_url: settings.base_url.trim(),
        organization_id: settings.organization_id.trim(),
      };
      if (settings.api_key) {
        payload.api_key = settings.api_key;
      }
      const response = await api.post<{
        status: string;
        settings: AISettingsResponse;
      }>("/settings/ai", payload);
      setConfigured(true);
      setApiKeySet(true);
      setSource("secret");
      setEnvOverride(false);
      setSettings((prev) => ({ ...prev, api_key: "" }));
      setSuccessMessage(
        response?.status ||
          "AI settings saved. Workflow Builder and incident AI will use these credentials."
      );
      await mutate(AI_SETTINGS_SWR_KEY);
      await loadModels();
    } catch (err) {
      if (err instanceof KeepApiError) {
        setErrorMessage(err.message || "Failed to save AI settings");
      } else {
        setErrorMessage("An unexpected error occurred");
      }
    } finally {
      setIsSaving(false);
    }
  };

  const onDelete = async () => {
    setErrorMessage("");
    setSuccessMessage("");
    setTestResult(null);
    setIsDeleting(true);
    try {
      await api.delete("/settings/ai");
      setConfigured(false);
      setApiKeySet(false);
      setSource(null);
      setSettings({
        api_key: "",
        model: "gpt-4o-mini",
        base_url: "",
        organization_id: "",
      });
      setSuccessMessage("AI settings deleted");
      await mutate(AI_SETTINGS_SWR_KEY);
    } catch (err) {
      if (err instanceof KeepApiError) {
        setErrorMessage(err.message || "Failed to delete AI settings");
      } else {
        setErrorMessage("An unexpected error occurred");
      }
    } finally {
      setIsDeleting(false);
    }
  };

  const onTest = async () => {
    setErrorMessage("");
    setSuccessMessage("");
    setTestResult(null);
    if (!settings.api_key && !apiKeySet) {
      setErrorMessage("API key is required to test connectivity");
      return;
    }
    if (!settings.model.trim()) {
      setErrorMessage("Model is required to test connectivity");
      return;
    }

    setIsTesting(true);
    try {
      const payload: Record<string, string> = {
        model: settings.model.trim(),
        base_url: settings.base_url.trim(),
        organization_id: settings.organization_id.trim(),
      };
      if (settings.api_key) {
        payload.api_key = settings.api_key;
      }
      const response = await api.post<{
        success: boolean;
        message: string;
      }>("/settings/ai/test", payload);
      setTestResult({
        success: Boolean(response?.success),
        message: response?.message || "Connectivity test succeeded",
      });
    } catch (err) {
      if (err instanceof KeepApiError) {
        setTestResult({
          success: false,
          message:
            err.responseJson?.message ||
            err.message ||
            "Connectivity test failed",
        });
      } else {
        setTestResult({
          success: false,
          message: "An unexpected error occurred during the connectivity test",
        });
      }
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <div className="flex flex-col gap-4 max-w-2xl">
      <div>
        <Title>AI Assistant</Title>
        <PageSubtitle>
          Configure the OpenAI API key and default model used by Workflow
          Builder AI, incident chat, and related assistant features. Values are
          stored securely per tenant.
        </PageSubtitle>
      </div>

      {envOverride && (
        <Callout title="Environment override" color="amber">
          An <code>OPENAI_API_KEY</code> (or <code>OPEN_AI_API_KEY</code>) is set
          on the server and takes precedence over Settings until removed.
        </Callout>
      )}

      {configured && !envOverride && (
        <Callout title="Configured" color="teal">
          AI is enabled
          {source ? ` (source: ${source})` : ""}
          {apiKeySet ? " · API key set" : ""}
          {settings.model ? ` · model: ${settings.model}` : ""}.
        </Callout>
      )}

      <div className="flex flex-col gap-3">
        <div>
          <Subtitle>
            API Key
            {apiKeySet ? " (leave blank to keep existing)" : ""}
          </Subtitle>
          <TextInput
            type="password"
            placeholder={apiKeySet ? "••••••••" : "sk-..."}
            value={settings.api_key}
            onChange={(e) =>
              setSettings((prev) => ({ ...prev, api_key: e.target.value }))
            }
          />
        </div>

        <div>
          <div className="flex items-center justify-between gap-2 mb-1">
            <Subtitle>Model</Subtitle>
            <Button
              size="xs"
              variant="secondary"
              loading={isLoadingModels}
              onClick={() => void loadModels()}
            >
              Refresh models
            </Button>
          </div>
          <Select
            className="z-20"
            placeholder="Select a model"
            isClearable={false}
            options={modelOptions}
            value={selectedModelOption}
            onChange={(option) =>
              setSettings((prev) => ({
                ...prev,
                model: option?.value || "",
              }))
            }
            onCreateOption={(inputValue) => {
              const custom = inputValue.trim();
              if (!custom) return;
              setModelOptions((prev) =>
                prev.some((o) => o.value === custom)
                  ? prev
                  : [{ value: custom, label: custom }, ...prev]
              );
              setSettings((prev) => ({ ...prev, model: custom }));
            }}
            isCreatable
          />
          <p className="text-xs text-gray-500 mt-1">
            Pick from models available to your key, or type a custom model name.
          </p>
        </div>

        <div>
          <Subtitle>Base URL (optional)</Subtitle>
          <TextInput
            placeholder="https://api.openai.com/v1 or LiteLLM proxy"
            value={settings.base_url}
            onChange={(e) =>
              setSettings((prev) => ({ ...prev, base_url: e.target.value }))
            }
          />
        </div>

        <div>
          <Subtitle>Organization ID (optional)</Subtitle>
          <TextInput
            placeholder="org-..."
            value={settings.organization_id}
            onChange={(e) =>
              setSettings((prev) => ({
                ...prev,
                organization_id: e.target.value,
              }))
            }
          />
        </div>
      </div>

      {errorMessage && (
        <Callout title="Error" color="rose">
          {errorMessage}
        </Callout>
      )}
      {successMessage && (
        <Callout title="Success" color="teal">
          {successMessage}
        </Callout>
      )}
      {testResult && (
        <Callout
          title={testResult.success ? "Connectivity OK" : "Connectivity failed"}
          color={testResult.success ? "teal" : "rose"}
        >
          {testResult.message}
        </Callout>
      )}

      <div className="flex flex-wrap gap-2">
        <Button color="orange" loading={isSaving} onClick={onSave}>
          Save AI settings
        </Button>
        <Button
          variant="secondary"
          color="orange"
          loading={isTesting}
          onClick={onTest}
        >
          Test connectivity
        </Button>
        {configured && !envOverride && (
          <Button
            variant="secondary"
            color="rose"
            loading={isDeleting}
            onClick={onDelete}
          >
            Delete
          </Button>
        )}
      </div>
    </div>
  );
}

export default AISettingsForm;
