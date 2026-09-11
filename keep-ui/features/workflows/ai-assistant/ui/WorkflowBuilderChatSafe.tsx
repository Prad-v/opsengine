import { useConfig } from "@/utils/hooks/useConfig";
import Image from "next/image";
import { SparklesIcon } from "@heroicons/react/24/outline";
import { Text, Title } from "@tremor/react";
import { Link } from "@/components/ui";
import { DefinitionV2 } from "@/entities/workflows";
import {
  WorkflowBuilderChat,
  WorkflowBuilderChatProps,
} from "./WorkflowBuilderChat";
import BuilderChatPlaceholder from "./ai-workflow-placeholder.png";
import { useAISettings } from "@/features/settings/ai";

type WorkflowBuilderChatSafeProps = Omit<
  WorkflowBuilderChatProps,
  "definition"
> & {
  definition: DefinitionV2 | null;
};

export function WorkflowBuilderChatSafe({
  definition,
  ...props
}: WorkflowBuilderChatSafeProps) {
  const { data: config } = useConfig();
  const { isAIEnabled, isLoading } = useAISettings();

  // AI requires env key or Settings → AI configuration
  if (!isLoading && !isAIEnabled) {
    const docsUrl = config?.KEEP_DOCS_URL
      ? `${config.KEEP_DOCS_URL.replace(/\/$/, "")}/overview/ai-workflow-assistant`
      : "https://docs.keephq.dev/overview/ai-workflow-assistant";
    return (
      <div className="flex flex-col items-center justify-center h-full relative">
        <Image
          src={BuilderChatPlaceholder}
          alt="Workflow AI Assistant"
          width={400}
          height={895}
          className="w-full h-full object-cover object-top max-w-[500px] mx-auto absolute inset-0"
        />
        <div className="w-full h-full absolute inset-0 bg-white/80" />
        <div className="flex flex-col items-center justify-center h-full z-10">
          <div className="flex flex-col items-center justify-center bg-[radial-gradient(circle,white_50%,transparent)] p-8 rounded-lg aspect-square max-w-sm text-center">
            <SparklesIcon className="size-10 text-orange-500" />
            <Title>AI is disabled</Title>
            <Text>
              Configure an OpenAI API key under{" "}
              <Link href="/settings?selectedTab=ai">Settings → AI</Link>, or set{" "}
              <code>OPENAI_API_KEY</code> in the frontend environment.
            </Text>
            <Link href={docsUrl} target="_blank" rel="noopener noreferrer">
              Setup guide
            </Link>
          </div>
        </div>
      </div>
    );
  }

  if (definition == null || isLoading) {
    return null;
  }

  return <WorkflowBuilderChat definition={definition} {...props} />;
}
