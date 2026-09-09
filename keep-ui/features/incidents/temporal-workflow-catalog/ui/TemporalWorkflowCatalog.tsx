"use client";

import { useState } from "react";
import {
  Badge,
  Button,
  Callout,
  Card,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  Title,
  Text,
} from "@tremor/react";
import type { IncidentDto } from "@/entities/incidents/model";
import { showErrorToast, showSuccessToast } from "@/shared/ui";
import { DynamicImageProviderIcon } from "@/components/ui";
import {
  useTemporalWorkflowCatalog,
} from "../model/useTemporalWorkflowCatalog";
import type { TemporalCatalogEntry } from "../model/types";

interface TemporalWorkflowCatalogProps {
  incident: IncidentDto;
}

export function TemporalWorkflowCatalog({
  incident,
}: TemporalWorkflowCatalogProps) {
  const {
    temporalProviders,
    catalog,
    error,
    isLoading,
    startCatalogWorkflow,
    mutate,
  } = useTemporalWorkflowCatalog(incident);
  const [startingId, setStartingId] = useState<string | null>(null);

  const linked =
    (incident.enrichments?.temporal_workflows as
      | Array<{
          catalog_id?: string;
          catalog_name?: string;
          workflow_id?: string;
          run_id?: string;
          workflow_type?: string;
          started_at?: string;
        }>
      | undefined) ?? [];

  if (!isLoading && temporalProviders.length === 0) {
    return (
      <Card className="mb-4">
        <Title>Temporal workflow catalog</Title>
        <Text className="mt-2">
          Install and configure a Temporal provider with a Keep-managed{" "}
          <code>workflow_catalog</code> to start Temporal workflows from this
          incident.
        </Text>
      </Card>
    );
  }

  const handleStart = async (entry: TemporalCatalogEntry) => {
    const key = `${entry.provider_id}:${entry.id}`;
    setStartingId(key);
    try {
      const result = await startCatalogWorkflow(entry);
      showSuccessToast(
        `Started Temporal workflow ${result.workflow_id}${
          result.run_id ? ` (run ${result.run_id})` : ""
        }`
      );
      await mutate();
    } catch (err) {
      showErrorToast(err, "Failed to start Temporal workflow from catalog");
    } finally {
      setStartingId(null);
    }
  };

  return (
    <Card className="mb-4">
      <div className="flex items-start justify-between gap-4 mb-3">
        <div>
          <Title>Temporal workflow catalog</Title>
          <Text className="mt-1">
            Keep-managed Temporal workflows configured on your Temporal
            provider. Start one to pass this incident as workflow input.
          </Text>
        </div>
        <Button variant="secondary" size="xs" onClick={() => mutate()}>
          Refresh
        </Button>
      </div>

      {error && (
        <Callout
          className="mb-3"
          title="Failed to load Temporal catalog"
          color="rose"
        >
          {error instanceof Error ? error.message : String(error)}
        </Callout>
      )}

      {isLoading ? (
        <Text>Loading Temporal catalog...</Text>
      ) : error ? null : catalog.length === 0 ? (
        <Callout
          title="Catalog is empty"
          color="orange"
          className="mb-2"
        >
          Add a JSON <code>workflow_catalog</code> on the Temporal provider
          configuration to list available workflows here. Example entry needs{" "}
          <code>id</code>, <code>workflow_type</code>, and{" "}
          <code>task_queue</code>.
        </Callout>
      ) : (
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Name</TableHeaderCell>
              <TableHeaderCell>Type</TableHeaderCell>
              <TableHeaderCell>Task queue</TableHeaderCell>
              <TableHeaderCell>Provider</TableHeaderCell>
              <TableHeaderCell>Action</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {catalog.map((entry) => {
              const key = `${entry.provider_id}:${entry.id}`;
              return (
                <TableRow key={key}>
                  <TableCell>
                    <div className="flex flex-col">
                      <span className="font-medium">{entry.name}</span>
                      {entry.description ? (
                        <span className="text-xs text-tremor-content">
                          {entry.description}
                        </span>
                      ) : null}
                    </div>
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
                      <span>{entry.provider_name}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Button
                      size="xs"
                      color="orange"
                      loading={startingId === key}
                      disabled={startingId !== null}
                      onClick={() => handleStart(entry)}
                    >
                      Start for incident
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}

      {linked.length > 0 && (
        <div className="mt-4">
          <Text className="font-medium mb-2">Linked Temporal runs</Text>
          <div className="flex flex-col gap-2">
            {linked.map((item, index) => (
              <div
                key={`${item.workflow_id}-${item.run_id}-${index}`}
                className="flex flex-wrap items-center gap-2 text-sm"
              >
                <Badge color="emerald">
                  {item.catalog_name || item.catalog_id || "catalog"}
                </Badge>
                <code>{item.workflow_id}</code>
                {item.run_id ? <span>run {item.run_id}</span> : null}
                {item.workflow_type ? (
                  <Badge color="indigo">{item.workflow_type}</Badge>
                ) : null}
                {item.started_at ? (
                  <span className="text-tremor-content">
                    {new Date(item.started_at).toLocaleString()}
                  </span>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}
