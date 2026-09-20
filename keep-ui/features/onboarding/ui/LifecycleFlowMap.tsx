"use client";

import { useMemo } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  ReactFlow,
  ReactFlowProvider,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { LifecycleRow } from "../model/lifecycleRows";
import { buildLifecycleFlowGraph } from "../model/buildLifecycleFlowGraph";
import { LifecycleFlowNode } from "./LifecycleFlowNode";

const nodeTypes = {
  lifecycle: LifecycleFlowNode,
};

interface LifecycleFlowMapProps {
  row: LifecycleRow;
}

function LifecycleFlowCanvas({ row }: LifecycleFlowMapProps) {
  const { nodes, edges } = useMemo(() => buildLifecycleFlowGraph(row), [row]);

  return (
    <div
      className="h-52 w-full overflow-hidden rounded-md border border-gray-200 bg-gray-50"
      data-testid="lifecycle-flow-map"
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2, minZoom: 0.5, maxZoom: 1.2 }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        panOnDrag
        zoomOnScroll={false}
        preventScrolling={false}
        proOptions={{ hideAttribution: true }}
        minZoom={0.4}
        maxZoom={1.5}
      >
        <Background variant={BackgroundVariant.Dots} gap={16} size={1} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

export function LifecycleFlowMap({ row }: LifecycleFlowMapProps) {
  return (
    <ReactFlowProvider>
      <LifecycleFlowCanvas row={row} />
    </ReactFlowProvider>
  );
}
