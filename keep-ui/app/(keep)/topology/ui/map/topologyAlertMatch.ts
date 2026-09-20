import { AlertDto } from "@/entities/alerts/model";
import { IncidentDto, Status } from "@/entities/incidents/model";
import { TopologyService } from "@/app/(keep)/topology/model";

export const LOCATION_LABELS = [
  "host",
  "rack",
  "row",
  "datacenter",
  "region",
  "gpu_id",
] as const;

export const ACTIVE_INCIDENT_STATUSES: Status[] = [
  Status.Firing,
  Status.Acknowledged,
];

export const HISTORICAL_INCIDENT_STATUSES: Status[] = [
  Status.Resolved,
  Status.Merged,
];

export function alertMatchesTopologyService(
  alert: Pick<AlertDto, "service" | "labels">,
  service: Pick<TopologyService, "service">
): boolean {
  if (alert.service === service.service) {
    return true;
  }
  const labels = alert.labels || {};
  return LOCATION_LABELS.some((key) => labels[key] === service.service);
}

function serviceNames(service: Pick<TopologyService, "service" | "display_name">) {
  return [service.service, service.display_name].filter(Boolean);
}

export function incidentMatchesTopologyService(
  incident: Pick<IncidentDto, "id" | "services" | "enrichments">,
  service: Pick<TopologyService, "service" | "display_name">,
  alerts: Pick<AlertDto, "service" | "labels" | "incident">[] = []
): boolean {
  const names = serviceNames(service);
  if (incident.services?.some((value) => names.includes(value))) {
    return true;
  }
  const enrichments = incident.enrichments || {};
  if (
    LOCATION_LABELS.some((key) => names.includes(String(enrichments[key] ?? "")))
  ) {
    return true;
  }
  return alerts.some(
    (alert) =>
      alert.incident === incident.id &&
      alertMatchesTopologyService(alert, service)
  );
}

export function isActiveIncidentStatus(status: Status): boolean {
  return ACTIVE_INCIDENT_STATUSES.includes(status);
}

export function isHistoricalIncidentStatus(status: Status): boolean {
  return HISTORICAL_INCIDENT_STATUSES.includes(status);
}
