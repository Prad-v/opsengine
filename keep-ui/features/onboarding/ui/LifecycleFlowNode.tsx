"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import clsx from "clsx";
import { Link } from "@/components/ui";
import type {
  LifecycleFlowNode as LifecycleFlowNodeType,
  LifecycleFlowNodeData,
} from "../model/buildLifecycleFlowGraph";

const stageAccent: Record<LifecycleFlowNodeData["stage"], string> = {
  correlation: "border-sky-400",
  incident: "border-orange-400",
  workflow: "border-emerald-400",
};

export function LifecycleFlowNode({
  data,
}: NodeProps<LifecycleFlowNodeType>) {
  const body = (
    <div
      className={clsx(
        "w-[168px] rounded-md border-2 bg-white px-3 py-2 shadow-sm",
        data.wired ? stageAccent[data.stage] : "border-dashed border-gray-300",
        !data.wired && "opacity-70"
      )}
      data-testid={`lifecycle-flow-node-${data.stage}`}
    >
      <p className="text-[10px] font-semibold uppercase tracking-wide text-gray-500">
        {data.title}
      </p>
      <p
        className={clsx(
          "mt-0.5 truncate text-sm font-medium text-gray-900",
          data.href && "text-orange-600 hover:underline"
        )}
        title={data.subtitle}
      >
        {data.subtitle}
      </p>
      {data.badge ? (
        <p className="mt-1 truncate text-[10px] text-gray-500">{data.badge}</p>
      ) : null}
      {!data.wired ? (
        <p className="mt-1 text-[10px] text-amber-600">Not wired</p>
      ) : null}
    </div>
  );

  return (
    <>
      {data.stage !== "correlation" ? (
        <Handle
          type="target"
          position={Position.Left}
          className="!h-2 !w-2 !border-gray-400 !bg-white"
        />
      ) : null}
      {data.href ? (
        <Link href={data.href} className="block no-underline">
          {body}
        </Link>
      ) : (
        body
      )}
      {data.stage !== "workflow" ? (
        <Handle
          type="source"
          position={Position.Right}
          className="!h-2 !w-2 !border-gray-400 !bg-white"
        />
      ) : null}
    </>
  );
}
