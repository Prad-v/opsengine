"use client";

import {
  Badge,
  Callout,
  MultiSelect,
  MultiSelectItem,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  Text,
} from "@tremor/react";
import { useMemo, useState } from "react";
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
  const [selectedTags, setSelectedTags] = useState<string[]>([]);

  const availableTags = useMemo(() => {
    const tags = catalog.flatMap((entry) => entry.tags ?? []);
    return Array.from(new Set(tags.map((tag) => tag.trim().toLowerCase()).filter(Boolean))).sort();
  }, [catalog]);

  const filteredCatalog = useMemo(() => {
    if (selectedTags.length === 0) {
      return catalog;
    }
    const required = new Set(selectedTags.map((tag) => tag.toLowerCase()));
    return catalog.filter((entry) => {
      const entryTags = new Set(
        (entry.tags ?? []).map((tag) => tag.trim().toLowerCase())
      );
      return Array.from(required).every((tag) => entryTags.has(tag));
    });
  }, [catalog, selectedTags]);

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
    <div className="flex flex-col gap-3">
      {availableTags.length > 0 ? (
        <div>
          <Text className="mb-1">Filter by tags</Text>
          <MultiSelect
            value={selectedTags}
            onValueChange={setSelectedTags}
            placeholder="All tags"
          >
            {availableTags.map((tag) => (
              <MultiSelectItem key={tag} value={tag}>
                {tag}
              </MultiSelectItem>
            ))}
          </MultiSelect>
        </div>
      ) : null}

      {filteredCatalog.length === 0 ? (
        <Callout title="No matching codes" color="orange">
          No alert codes match the selected tags. Clear the tag filter to see
          all codes.
        </Callout>
      ) : (
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Code</TableHeaderCell>
              <TableHeaderCell>Name</TableHeaderCell>
              <TableHeaderCell>Tags</TableHeaderCell>
              <TableHeaderCell>Workflow</TableHeaderCell>
              <TableHeaderCell>Auto-run</TableHeaderCell>
              {renderActions ? <TableHeaderCell>Actions</TableHeaderCell> : null}
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredCatalog.map((entry) => (
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
                  {(entry.tags ?? []).length > 0 ? (
                    <div className="flex flex-wrap gap-1">
                      {(entry.tags ?? []).map((tag) => (
                        <Badge key={tag} color="orange" size="xs">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  ) : (
                    <Text className="text-xs">—</Text>
                  )}
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
      )}
    </div>
  );
}
