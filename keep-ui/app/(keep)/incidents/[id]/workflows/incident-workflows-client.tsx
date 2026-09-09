"use client";

import type { IncidentDto } from "@/entities/incidents/model";
import IncidentWorkflowTable from "./incident-workflow-table";
import { TemporalWorkflowCatalog } from "@/features/incidents/temporal-workflow-catalog";

interface Props {
  incident: IncidentDto;
}

export default function IncidentWorkflowsClient({ incident }: Props) {
  return (
    <div className="flex flex-col gap-4">
      <TemporalWorkflowCatalog incident={incident} />
      <IncidentWorkflowTable incident={incident} />
    </div>
  );
}
