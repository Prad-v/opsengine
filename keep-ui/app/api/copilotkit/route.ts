import {
  CopilotRuntime,
  OpenAIAdapter,
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";
import OpenAI, { OpenAIError } from "openai";
import { NextRequest } from "next/server";
import { createServerApiClient } from "@/shared/api/server/createServerApiClient";

type AIRuntimeSettings = {
  api_key?: string | null;
  model?: string | null;
  base_url?: string | null;
  organization_id?: string | null;
  configured?: boolean;
};

function getEnvOpenAiApiKey(): string | undefined {
  return process.env.OPEN_AI_API_KEY || process.env.OPENAI_API_KEY;
}

async function resolveOpenAiRuntime(): Promise<AIRuntimeSettings> {
  const envKey = getEnvOpenAiApiKey();
  if (envKey) {
    return {
      api_key: envKey,
      model: process.env.OPENAI_MODEL_NAME || null,
      base_url: process.env.OPENAI_BASE_URL || null,
      organization_id: process.env.OPEN_AI_ORGANIZATION_ID || null,
      configured: true,
    };
  }

  try {
    const api = await createServerApiClient();
    const runtime = await api.get<AIRuntimeSettings>("/settings/ai/runtime");
    return runtime || { configured: false };
  } catch (error) {
    console.error("Failed to load AI settings from backend", error);
    return { configured: false };
  }
}

export const POST = async (req: NextRequest) => {
  async function initializeCopilotRuntime() {
    try {
      const runtimeSettings = await resolveOpenAiRuntime();
      const apiKey = runtimeSettings.api_key || undefined;
      if (!apiKey) {
        console.error(
          "OpenAI API key is not set. Configure it under Settings → AI, or set OPENAI_API_KEY / OPEN_AI_API_KEY."
        );
        return null;
      }

      const openai = new OpenAI({
        organization: runtimeSettings.organization_id || undefined,
        apiKey,
        ...(runtimeSettings.base_url
          ? { baseURL: runtimeSettings.base_url }
          : {}),
      });
      const serviceAdapter = new OpenAIAdapter({
        openai,
        ...(runtimeSettings.model ? { model: runtimeSettings.model } : {}),
      });
      const runtime = new CopilotRuntime();
      return { runtime, serviceAdapter };
    } catch (error) {
      if (error instanceof OpenAIError) {
        console.log("Error connecting to OpenAI", error);
      } else {
        console.error("Error initializing Copilot Runtime", error);
      }
      return null;
    }
  }

  const runtimeOptions = await initializeCopilotRuntime();

  if (!runtimeOptions) {
    return new Response("Error initializing Copilot Runtime", { status: 500 });
  }
  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime: runtimeOptions.runtime,
    serviceAdapter: runtimeOptions.serviceAdapter,
    endpoint: "/api/copilotkit",
  });

  return handleRequest(req);
};
