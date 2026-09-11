"use client";

import {
  Badge,
  Callout,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  Text,
} from "@tremor/react";
import { DynamicImageProviderIcon } from "@/components/ui";
import type { SyntheticCheck } from "../model/types";
import type { ReactNode } from "react";

interface SyntheticCheckTableProps {
  checks: SyntheticCheck[];
  isLoading?: boolean;
  error?: unknown;
  emptyMessage?: ReactNode;
  renderActions?: (entry: SyntheticCheck) => ReactNode;
}

export function SyntheticCheckTable({
  checks,
  isLoading,
  error,
  emptyMessage,
  renderActions,
}: SyntheticCheckTableProps) {
  if (isLoading) {
    return <Text>Loading synthetic checks...</Text>;
  }

  if (error) {
    return (
      <Callout
        className="mb-3"
        title="Failed to load synthetic checks"
        color="rose"
      >
        {error instanceof Error ? error.message : String(error)}
      </Callout>
    );
  }

  if (checks.length === 0) {
    return (
      <Callout title="No synthetic checks" color="orange" className="mb-2">
        {emptyMessage ?? (
          <>
            Create HTTP/TCP/DNS checks here. Keep syncs a Temporal Schedule for
            each enabled check on queue <code>keep-synth</code>.
          </>
        )}
      </Callout>
    );
  }

  return (
    <Table>
      <TableHead>
        <TableRow>
          <TableHeaderCell>Name</TableHeaderCell>
          <TableHeaderCell>Prober</TableHeaderCell>
          <TableHeaderCell>Targets</TableHeaderCell>
          <TableHeaderCell>Interval</TableHeaderCell>
          <TableHeaderCell>Provider</TableHeaderCell>
          {renderActions ? <TableHeaderCell>Actions</TableHeaderCell> : null}
        </TableRow>
      </TableHead>
      <TableBody>
        {checks.map((entry) => (
          <TableRow key={entry.id}>
            <TableCell>
              <div className="flex flex-col">
                <span className="font-medium">{entry.name}</span>
                <code className="text-xs">{entry.check_key}</code>
                {!entry.enabled ? (
                  <Badge color="gray" size="xs" className="mt-1 w-fit">
                    Disabled
                  </Badge>
                ) : null}
              </div>
            </TableCell>
            <TableCell>
              <Badge color="indigo">{entry.prober}</Badge>
            </TableCell>
            <TableCell>
              <Text className="text-xs">
                {(entry.targets || []).slice(0, 3).join(", ")}
                {(entry.targets || []).length > 3
                  ? ` (+${(entry.targets || []).length - 3})`
                  : ""}
              </Text>
            </TableCell>
            <TableCell>{entry.interval_seconds}s</TableCell>
            <TableCell>
              <div className="flex items-center gap-2">
                <DynamicImageProviderIcon
                  providerType="temporal"
                  width={20}
                  height={20}
                />
                <span>
                  {entry.provider_name || entry.temporal_provider_id}
                </span>
              </div>
            </TableCell>
            {renderActions ? (
              <TableCell>
                <div className="flex flex-wrap gap-2">
                  {renderActions(entry)}
                </div>
              </TableCell>
            ) : null}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
