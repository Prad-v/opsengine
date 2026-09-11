"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Badge,
  Button,
  Card,
  Title,
  Text,
} from "@tremor/react";
import type { IncidentDto } from "@/entities/incidents/model";
import { showErrorToast, showSuccessToast } from "@/shared/ui";
import {
  useStartTemporalCatalogWorkflow,
  useTemporalWorkflowCatalog,
} from "../model/useTemporalWorkflowCatalog";
import type { TemporalCatalogEntry, TemporalLinkedRun } from "../model/types";
import { TemporalCatalogTable } from "./TemporalCatalogTable";

interface TemporalWorkflowIncidentRegistrationProps {
  incident: IncidentDto;
}

export function TemporalWorkflowIncidentRegistration({
  incident,
}: TemporalWorkflowIncidentRegistrationProps) {
  const { catalog, error, isLoading, mutate } = useTemporalWorkflowCatalog();
  const { startCatalogWorkflow } = useStartTemporalCatalogWorkflow(incident);
  const [startingId, setStartingId] = useState<number | null>(null);

  const linked =
    (incident.enrichments?.temporal_workflows as
      | TemporalLinkedRun[]
      | undefined) ?? [];

  const enabledCatalog = catalog.filter((entry) => !entry.disabled);

  const handleStart = async (entry: TemporalCatalogEntry) => {
    setStartingId(entry.id);
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
          <Title>Temporal workflow registration</Title>
          <Text className="mt-1">
            Start a registered Temporal workflow for this incident. Manage the
            catalog under{" "}
            <Link
              href="/catalog/temporal-workflows"
              className="text-orange-500 underline"
            >
              Catalog → Temporal workflow
            </Link>
            .
          </Text>
        </div>
        <Button variant="secondary" size="xs" onClick={() => mutate()}>
          Refresh
        </Button>
      </div>

      <TemporalCatalogTable
        catalog={enabledCatalog}
        isLoading={isLoading}
        error={error}
        emptyMessage={
          <>
            No Temporal workflows registered. Add them under{" "}
            <Link
              href="/catalog/temporal-workflows"
              className="underline"
            >
              Catalog → Temporal workflow
            </Link>
            .
          </>
        }
        renderActions={(entry) => (
          <Button
            size="xs"
            color="orange"
            loading={startingId === entry.id}
            disabled={startingId !== null}
            onClick={() => handleStart(entry)}
          >
            Start for incident
          </Button>
        )}
      />

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
