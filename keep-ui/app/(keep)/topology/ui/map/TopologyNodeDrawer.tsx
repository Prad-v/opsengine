"use client";

import { useEffect, useMemo, useState } from "react";
import SidePanel from "@/components/SidePanel";
import { TopologyService } from "@/app/(keep)/topology/model";
import { AlertDto } from "@/entities/alerts/model";
import { IncidentDto } from "@/entities/incidents/model";
import { IncidentIconName, IncidentSeverityBadge } from "@/entities/incidents/ui";
import { Link } from "@/components/ui";
import {
  Button,
  Select,
  SelectItem,
  Textarea,
  Badge,
} from "@tremor/react";
import { XMarkIcon } from "@heroicons/react/24/outline";
import { useMaintenanceRules } from "@/utils/hooks/useMaintenanceRules";
import { remainingLabel } from "@/app/(keep)/maintenance/lib/maintenanceRuleUtils";
import { showErrorToast, showSuccessToast } from "@/shared/ui";
import { isApprovalPending, useApprovals } from "@/features/approvals";
import { TopologyCategoryIcon } from "./topologyNodeIcons";
import {
  HISTORICAL_INCIDENT_STATUSES,
  incidentMatchesTopologyService,
  isActiveIncidentStatus,
} from "./topologyAlertMatch";
import {
  TOPOLOGY_MAINTENANCE_DURATIONS,
  TOPOLOGY_MAINTENANCE_REASONS,
  TopologyMaintenanceReasonId,
  findActiveMaintenanceRule,
  findPendingNodeMaintenance,
  maintenanceCelForService,
  topologyMaintenanceRuleName,
} from "./topologyMaintenance";

export type TopologyNodeDrawerProps = {
  isOpen: boolean;
  onClose: () => void;
  service: TopologyService | null;
  incidents: IncidentDto[];
  alerts: AlertDto[];
};

function formatIncidentTime(value?: Date | string | null): string | null {
  if (!value) {
    return null;
  }
  const parsed = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return String(value);
  }
  return parsed.toLocaleString();
}

function IncidentList({
  incidents,
  emptyLabel,
}: {
  incidents: IncidentDto[];
  emptyLabel: string;
}) {
  if (incidents.length === 0) {
    return <p className="text-sm text-gray-500">{emptyLabel}</p>;
  }
  return (
    <ul className="flex flex-col gap-2">
      {incidents.map((incident) => (
        <li
          key={incident.id}
          className="border border-gray-200 rounded-md p-2 hover:border-tremor-brand/50"
        >
          <Link
            href={`/incidents/${incident.id}`}
            className="font-semibold no-underline border-b-0"
          >
            <IncidentIconName incident={incident} inline />
          </Link>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-gray-500">
            <IncidentSeverityBadge severity={incident.severity} />
            <span className="capitalize">{incident.status}</span>
            {formatIncidentTime(incident.last_seen_time || incident.creation_time) ? (
              <span>
                {formatIncidentTime(
                  incident.last_seen_time || incident.creation_time
                )}
              </span>
            ) : null}
          </div>
        </li>
      ))}
    </ul>
  );
}

export function TopologyNodeDrawer({
  isOpen,
  onClose,
  service,
  incidents,
  alerts,
}: TopologyNodeDrawerProps) {
  const { data: rules, createRule, endNow } = useMaintenanceRules();
  const { requests: pendingApprovals } = useApprovals({
    status: "pending",
    actionType: "node_maintenance",
  });
  const [reasonId, setReasonId] =
    useState<TopologyMaintenanceReasonId>("node_down");
  const [otherReason, setOtherReason] = useState("");
  const [durationId, setDurationId] = useState("4h");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    setReasonId("node_down");
    setOtherReason("");
    setDurationId("4h");
  }, [service?.id]);

  const matchingIncidents = useMemo(() => {
    if (!service) {
      return [];
    }
    return incidents.filter((incident) =>
      incidentMatchesTopologyService(incident, service, alerts)
    );
  }, [alerts, incidents, service]);

  const activeIncidents = matchingIncidents.filter((incident) =>
    isActiveIncidentStatus(incident.status)
  );
  const historicalIncidents = matchingIncidents.filter((incident) =>
    HISTORICAL_INCIDENT_STATUSES.includes(incident.status)
  );

  const activeRule = service
    ? findActiveMaintenanceRule(rules, service.service)
    : undefined;
  const pendingRequest = service
    ? findPendingNodeMaintenance(pendingApprovals, service.service)
    : undefined;

  const reasonLabel =
    TOPOLOGY_MAINTENANCE_REASONS.find((reason) => reason.id === reasonId)
      ?.label ?? "Node down";
  const durationSeconds =
    TOPOLOGY_MAINTENANCE_DURATIONS.find((item) => item.id === durationId)
      ?.seconds ?? 4 * 3600;

  const handlePutInMaintenance = async () => {
    if (!service) {
      return;
    }
    if (reasonId === "other" && !otherReason.trim()) {
      showErrorToast(new Error("Describe why this node is in maintenance"));
      return;
    }
    const description =
      reasonId === "other" ? otherReason.trim() : reasonLabel;
    setIsSubmitting(true);
    try {
      await createRule({
        name: topologyMaintenanceRuleName(
          service.display_name || service.service,
          reasonLabel
        ),
        description,
        cel_query: maintenanceCelForService(service.service, service.category),
        start_time: new Date().toISOString(),
        duration_seconds: durationSeconds,
        suppress: true,
        enabled: true,
        ignore_statuses: ["resolved", "acknowledged"],
        topology_service_id: service.service,
        topology_category: service.category,
        topology_reason: reasonLabel,
      }).then((created) => {
        if (isApprovalPending(created)) {
          showSuccessToast(
            "Maintenance window submitted for approval. The node is not silenced yet."
          );
          return;
        }
        showSuccessToast(
          "Maintenance window created. Matching alerts are suppressed."
        );
      });
    } catch (error) {
      showErrorToast(error, "Failed to put node in maintenance");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleEndNow = async () => {
    if (!activeRule?.id) {
      return;
    }
    setIsSubmitting(true);
    try {
      await endNow(activeRule.id);
      showSuccessToast("Maintenance window ended");
    } catch (error) {
      showErrorToast(error, "Failed to end maintenance");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <SidePanel isOpen={isOpen} onClose={onClose} panelWidth="w-[28rem] max-w-full">
      <div className="flex items-start justify-between gap-3 pb-4 border-b border-gray-200">
        <div className="flex items-start gap-3 min-w-0">
          <TopologyCategoryIcon
            category={service?.category}
            className="h-7 w-7 text-gray-600 mt-0.5"
          />
          <div className="min-w-0">
            <h2 className="text-lg font-semibold truncate">
              {service?.display_name || service?.service || "Node"}
            </h2>
            <p className="text-xs text-gray-500 truncate">{service?.service}</p>
            <div className="mt-1 flex flex-wrap gap-1">
              {service?.category ? (
                <Badge color="gray" size="xs">
                  {service.category}
                </Badge>
              ) : null}
              {activeRule ? (
                <Badge color="amber" size="xs">
                  In maintenance
                </Badge>
              ) : null}
              {pendingRequest ? (
                <Badge color="orange" size="xs">
                  Pending approval
                </Badge>
              ) : null}
            </div>
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-gray-400 hover:text-gray-700"
          aria-label="Close"
        >
          <XMarkIcon className="h-5 w-5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto py-4 flex flex-col gap-6">
        {service?.description ? (
          <p className="text-sm text-gray-600">{service.description}</p>
        ) : null}

        <section>
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold">Maintenance</h3>
            <Link href="/maintenance" className="text-xs font-normal">
              All windows
            </Link>
          </div>
          {activeRule ? (
            <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm">
              <p className="font-medium">{activeRule.name}</p>
              {activeRule.description ? (
                <p className="text-gray-600 mt-1">{activeRule.description}</p>
              ) : null}
              <p className="text-xs text-gray-500 mt-1 font-mono break-all">
                {activeRule.cel_query}
              </p>
              {remainingLabel(activeRule.end_time) ? (
                <p className="text-xs text-amber-800 mt-1">
                  {remainingLabel(activeRule.end_time)}
                </p>
              ) : null}
              <Button
                className="mt-3"
                color="amber"
                size="xs"
                variant="secondary"
                disabled={isSubmitting}
                onClick={handleEndNow}
              >
                End now
              </Button>
            </div>
          ) : pendingRequest ? (
            <div className="rounded-md border border-orange-200 bg-orange-50 p-3">
              <p className="text-sm font-medium text-orange-900">
                Maintenance is waiting for approval
              </p>
              <p className="text-xs text-orange-800 mt-1">
                Alerts are not suppressed until an approver accepts the request.
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              <label className="text-xs text-gray-500">Reason</label>
              <Select
                value={reasonId}
                onValueChange={(value) =>
                  setReasonId(value as TopologyMaintenanceReasonId)
                }
              >
                {TOPOLOGY_MAINTENANCE_REASONS.map((reason) => (
                  <SelectItem key={reason.id} value={reason.id}>
                    {reason.label}
                  </SelectItem>
                ))}
              </Select>
              {reasonId === "other" ? (
                <Textarea
                  placeholder="Describe the work (required)"
                  value={otherReason}
                  onChange={(event) => setOtherReason(event.target.value)}
                />
              ) : null}
              <label className="text-xs text-gray-500 mt-1">Duration</label>
              <Select value={durationId} onValueChange={setDurationId}>
                {TOPOLOGY_MAINTENANCE_DURATIONS.map((item) => (
                  <SelectItem key={item.id} value={item.id}>
                    {item.label}
                  </SelectItem>
                ))}
              </Select>
              <p className="text-xs text-gray-500">
                Creates a Maintenance Windows rule that suppresses matching
                alerts for this resource.
              </p>
              <Button
                color="orange"
                size="sm"
                disabled={!service || isSubmitting}
                onClick={handlePutInMaintenance}
              >
                Put node in maintenance
              </Button>
            </div>
          )}
        </section>

        <section>
          <h3 className="text-sm font-semibold mb-2">
            Active incidents ({activeIncidents.length})
          </h3>
          <IncidentList
            incidents={activeIncidents}
            emptyLabel="No active incidents for this node."
          />
        </section>

        <section>
          <h3 className="text-sm font-semibold mb-2">
            Historical incidents ({historicalIncidents.length})
          </h3>
          <IncidentList
            incidents={historicalIncidents}
            emptyLabel="No resolved or merged incidents for this node."
          />
        </section>
      </div>
    </SidePanel>
  );
}
