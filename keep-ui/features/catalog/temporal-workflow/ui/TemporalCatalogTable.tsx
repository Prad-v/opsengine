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
import type { TemporalCatalogEntry } from "../model/types";
import type { ReactNode } from "react";

interface TemporalCatalogTableProps {
  catalog: TemporalCatalogEntry[];
  isLoading?: boolean;
  error?: unknown;
  emptyMessage?: ReactNode;
  renderActions?: (entry: TemporalCatalogEntry) => ReactNode;
}

export function TemporalCatalogTable({
  catalog,
  isLoading,
  error,
  emptyMessage,
  renderActions,
}: TemporalCatalogTableProps) {
  if (isLoading) {
    return <Text>Loading Temporal catalog...</Text>;
  }

  if (error) {
    return (
      <Callout
        className="mb-3"
        title="Failed to load Temporal catalog"
        color="rose"
      >
        {error instanceof Error ? error.message : String(error)}
      </Callout>
    );
  }

  if (catalog.length === 0) {
    return (
      <Callout title="Catalog is empty" color="orange" className="mb-2">
        {emptyMessage ?? (
          <>
            Register Temporal workflows here. Each entry needs a catalog key,
            workflow type, task queue, and Temporal provider.
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
          <TableHeaderCell>Key</TableHeaderCell>
          <TableHeaderCell>Type</TableHeaderCell>
          <TableHeaderCell>Task queue</TableHeaderCell>
          <TableHeaderCell>Provider</TableHeaderCell>
          {renderActions ? <TableHeaderCell>Actions</TableHeaderCell> : null}
        </TableRow>
      </TableHead>
      <TableBody>
        {catalog.map((entry) => (
          <TableRow key={entry.id}>
            <TableCell>
              <div className="flex flex-col">
                <span className="font-medium">{entry.name}</span>
                {entry.description ? (
                  <span className="text-xs text-tremor-content">
                    {entry.description}
                  </span>
                ) : null}
                {entry.disabled ? (
                  <Badge color="gray" size="xs" className="mt-1 w-fit">
                    Disabled
                  </Badge>
                ) : null}
              </div>
            </TableCell>
            <TableCell>
              <code className="text-xs">{entry.catalog_key}</code>
            </TableCell>
            <TableCell>
              <Badge color="indigo">{entry.workflow_type}</Badge>
            </TableCell>
            <TableCell>{entry.task_queue}</TableCell>
            <TableCell>
              <div className="flex items-center gap-2">
                <DynamicImageProviderIcon
                  providerType="temporal"
                  width={20}
                  height={20}
                />
                <span>{entry.provider_name || entry.provider_id}</span>
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
