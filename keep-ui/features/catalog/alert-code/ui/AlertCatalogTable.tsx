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
import type { AlertCatalogEntry } from "../model/types";
import type { ReactNode } from "react";

interface AlertCatalogTableProps {
  catalog: AlertCatalogEntry[];
  isLoading?: boolean;
  error?: unknown;
  emptyMessage?: ReactNode;
  renderActions?: (entry: AlertCatalogEntry) => ReactNode;
}

export function AlertCatalogTable({
  catalog,
  isLoading,
  error,
  emptyMessage,
  renderActions,
}: AlertCatalogTableProps) {
  if (isLoading) {
    return <Text>Loading alert catalog...</Text>;
  }

  if (error) {
    return (
      <Callout
        className="mb-3"
        title="Failed to load alert catalog"
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
            Register reserved alert codes here. Each code can attach a runbook
            and optionally auto-run a Keep workflow on alert or incident.
          </>
        )}
      </Callout>
    );
  }

  return (
    <Table>
      <TableHead>
        <TableRow>
          <TableHeaderCell>Code</TableHeaderCell>
          <TableHeaderCell>Name</TableHeaderCell>
          <TableHeaderCell>Workflow</TableHeaderCell>
          <TableHeaderCell>Auto-run</TableHeaderCell>
          {renderActions ? <TableHeaderCell>Actions</TableHeaderCell> : null}
        </TableRow>
      </TableHead>
      <TableBody>
        {catalog.map((entry) => (
          <TableRow key={entry.id}>
            <TableCell>
              <div className="flex items-center gap-2">
                <code className="text-sm">{entry.code}</code>
                {entry.disabled ? (
                  <Badge color="gray">disabled</Badge>
                ) : null}
              </div>
            </TableCell>
            <TableCell>
              <div className="flex flex-col">
                <span className="font-medium">{entry.name}</span>
                {entry.description ? (
                  <Text className="text-xs">{entry.description}</Text>
                ) : null}
              </div>
            </TableCell>
            <TableCell>
              {entry.keep_workflow_id ? (
                <code className="text-xs">{entry.keep_workflow_id}</code>
              ) : (
                <Text className="text-xs">—</Text>
              )}
            </TableCell>
            <TableCell>
              <Badge color={entry.auto_run_on === "none" ? "gray" : "orange"}>
                {entry.auto_run_on}
              </Badge>
            </TableCell>
            {renderActions ? (
              <TableCell>
                <div className="flex gap-2">{renderActions(entry)}</div>
              </TableCell>
            ) : null}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
