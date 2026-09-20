"use client";

import { Button, Text, Title } from "@tremor/react";
import { CheckCircleIcon } from "@heroicons/react/20/solid";
import { Drawer } from "@/shared/ui/Drawer";
import { Link } from "@/components/ui";
import type { LifecycleRow } from "../model/lifecycleRows";
import { LifecycleFlowMap } from "./LifecycleFlowMap";

interface LifecycleViewDrawerProps {
  row: LifecycleRow | null;
  isOpen: boolean;
  onClose: () => void;
  onEdit: (row: LifecycleRow) => void;
}

export function LifecycleViewDrawer({
  row,
  isOpen,
  onClose,
  onEdit,
}: LifecycleViewDrawerProps) {
  return (
    <Drawer isOpen={isOpen} onClose={onClose}>
      {row ? (
        <div className="space-y-4 p-2" data-testid="lifecycle-view">
          <div className="flex items-start justify-between gap-3">
            <div>
              <Title>{row.name}</Title>
              <Text className="mt-1">
                <code>{row.code}</code>
                {row.paused ? " · paused" : " · active"}
              </Text>
            </div>
            <Button
              color="orange"
              size="xs"
              onClick={() => onEdit(row)}
            >
              Edit
            </Button>
          </div>
          {row.description ? <Text>{row.description}</Text> : null}
          <Text className="text-sm">
            {row.completedCount} of {row.totalCount} steps wired
            {row.isComplete ? " — this lifecycle is complete." : "."}
          </Text>

          <div className="space-y-2">
            <p className="text-sm font-medium text-gray-900">
              Correlation → Incident → Workflow
            </p>
            <Text className="text-xs">
              Configured path for this reserved code. Solid edges are wired;
              dashed edges still need setup.
            </Text>
            <LifecycleFlowMap row={row} />
          </div>

          <ol className="space-y-3">
            {row.status.steps.map((step) => (
              <li key={step.id} className="flex items-start gap-2">
                <CheckCircleIcon
                  className={
                    step.complete
                      ? "mt-0.5 h-5 w-5 text-emerald-500"
                      : "mt-0.5 h-5 w-5 text-gray-300"
                  }
                />
                <div>
                  <p className="font-medium text-gray-900">{step.shortTitle}</p>
                  <Text className="text-xs">{step.description}</Text>
                </div>
              </li>
            ))}
          </ol>
          <div className="space-y-1 border-t border-gray-100 pt-3">
            {row.correlation ? (
              <Text>
                Correlation:{" "}
                <Link href={`/rules?id=${row.correlation.id}`}>
                  {row.correlation.name}
                </Link>
              </Text>
            ) : (
              <Text>No correlation rule yet.</Text>
            )}
            {row.workflow ? (
              <Text>
                Workflow:{" "}
                <Link href={`/workflows/${row.workflow.id}`}>
                  {row.workflow.name}
                </Link>{" "}
                (auto-run {row.autoRunOn})
              </Text>
            ) : (
              <Text>No workflow attached yet.</Text>
            )}
          </div>
        </div>
      ) : null}
    </Drawer>
  );
}
