"use client";

import type { IncidentDto } from "@/entities/incidents/model";
import IncidentWorkflowTable from "./incident-workflow-table";
import { TemporalWorkflowIncidentRegistration } from "@/features/catalog/temporal-workflow";

interface Props {
  incident: IncidentDto;
}

export default function IncidentWorkflowsClient({ incident }: Props) {
  return (
    <div className="flex flex-col gap-4">
      <TemporalWorkflowIncidentRegistration incident={incident} />
      <IncidentWorkflowTable incident={incident} />
    </div>
  );
}
