import type { Edge, Node } from "@xyflow/react";
import { MarkerType } from "@xyflow/react";
import type { LifecycleRow } from "./lifecycleRows";

export type LifecycleFlowStage = "correlation" | "incident" | "workflow";

export type LifecycleFlowNodeData = {
  stage: LifecycleFlowStage;
  title: string;
  subtitle: string;
  href?: string;
  wired: boolean;
  badge?: string;
};

export type LifecycleFlowNode = Node<LifecycleFlowNodeData, "lifecycle">;

const NODE_WIDTH = 168;
const NODE_GAP_X = 72;
const NODE_Y = 24;

function nodeX(index: number): number {
  return index * (NODE_WIDTH + NODE_GAP_X);
}

export function buildLifecycleFlowGraph(
  row: LifecycleRow
): { nodes: LifecycleFlowNode[]; edges: Edge[] } {
  const correlationWired = Boolean(row.correlation);
  const workflowWired = Boolean(row.workflow);

  const nodes: LifecycleFlowNode[] = [
    {
      id: "correlation",
      type: "lifecycle",
      position: { x: nodeX(0), y: NODE_Y },
      data: {
        stage: "correlation",
        title: "Correlation",
        subtitle: correlationWired
          ? row.correlation!.name
          : "No rule yet",
        href: correlationWired
          ? `/rules?id=${row.correlation!.id}`
          : undefined,
        wired: correlationWired,
      },
      draggable: false,
      selectable: false,
    },
    {
      id: "incident",
      type: "lifecycle",
      position: { x: nodeX(1), y: NODE_Y },
      data: {
        stage: "incident",
        title: "Incident",
        subtitle: row.code,
        wired: correlationWired,
        badge: row.paused ? "paused" : undefined,
      },
      draggable: false,
      selectable: false,
    },
    {
      id: "workflow",
      type: "lifecycle",
      position: { x: nodeX(2), y: NODE_Y },
      data: {
        stage: "workflow",
        title: "Workflow",
        subtitle: workflowWired
          ? row.workflow!.name
          : "Not attached",
        href: workflowWired
          ? `/workflows/${row.workflow!.id}`
          : undefined,
        wired: workflowWired,
        badge: workflowWired ? `auto-run ${row.autoRunOn}` : undefined,
      },
      draggable: false,
      selectable: false,
    },
  ];

  const edges: Edge[] = [
    {
      id: "correlation-incident",
      source: "correlation",
      target: "incident",
      label: "groups into",
      animated: correlationWired,
      style: {
        stroke: correlationWired ? "#f97316" : "#d1d5db",
        strokeDasharray: correlationWired ? undefined : "6 4",
      },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: correlationWired ? "#f97316" : "#d1d5db",
      },
      labelStyle: { fontSize: 10, fill: "#6b7280" },
      labelBgStyle: { fill: "#fff" },
      labelBgPadding: [4, 2] as [number, number],
    },
    {
      id: "incident-workflow",
      source: "incident",
      target: "workflow",
      label: workflowWired ? "triggers" : "auto-run",
      animated: workflowWired,
      style: {
        stroke: workflowWired ? "#f97316" : "#d1d5db",
        strokeDasharray: workflowWired ? undefined : "6 4",
      },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: workflowWired ? "#f97316" : "#d1d5db",
      },
      labelStyle: { fontSize: 10, fill: "#6b7280" },
      labelBgStyle: { fill: "#fff" },
      labelBgPadding: [4, 2] as [number, number],
    },
  ];

  return { nodes, edges };
}
