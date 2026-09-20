import React, { useEffect, useState } from "react";
import { Handle, NodeProps, NodeToolbar, Position } from "@xyflow/react";
import { useRouter } from "next/navigation";
import { ServiceNodeType, TopologyService } from "../../model/models";
import { Badge } from "@tremor/react";
import { getColorForUUID } from "@/app/(keep)/topology/lib/badge-colors";
import { clsx } from "clsx";
import { TopologyCategoryIcon } from "./topologyNodeIcons";

const THRESHOLD = 5;

function ServiceDetailsTooltip({ data }: { data: TopologyService }) {
  return (
    <div className="py-2 px-3 bg-tremor-background-muted border rounded shadow-lg flex flex-col gap-2 text-xs">
      {data.service && (
        <div>
          <p className="text-gray-500">Service</p>
          <span>{data.service}</span>
        </div>
      )}
      {data.display_name && (
        <div>
          <p className="text-gray-500">Display Name</p>
          <span>{data.display_name}</span>
        </div>
      )}
      {data.description && (
        <div>
          <p className="text-gray-500">Description</p>
          <span>{data.description}</span>
        </div>
      )}
      {data.team && (
        <div>
          <p className="text-gray-500">Team</p>
          <span>{data.team}</span>
        </div>
      )}
      {data.email && (
        <div>
          <p className="text-gray-500">Email</p>
          <span>{data.email}</span>
        </div>
      )}
      {data.slack && (
        <div>
          <p className="text-gray-500">Slack</p>
          <span>{data.slack}</span>
        </div>
      )}
      {data.ip_address && (
        <div>
          <p className="text-gray-500">IP Address</p>
          <span>{data.ip_address}</span>
        </div>
      )}
      {data.mac_address && (
        <div>
          <p className="text-gray-500">MAC Address</p>
          <span>{data.mac_address}</span>
        </div>
      )}
      {data.manufacturer && (
        <div>
          <p className="text-gray-500">Manufacturer</p>
          <span>{data.manufacturer}</span>
        </div>
      )}
      {data.category && (
        <div>
          <p className="text-gray-500">Category</p>
          <span>{data.category}</span>
        </div>
      )}
      {data.inMaintenance && (
        <div>
          <p className="text-amber-700 font-medium">In maintenance</p>
          <span>Alerts for this node are suppressed</span>
        </div>
      )}
      {data.pendingMaintenance && !data.inMaintenance && (
        <div>
          <p className="text-orange-700 font-medium">Pending maintenance</p>
          <span>Waiting for approval before alerts are suppressed</span>
        </div>
      )}
      <p className="text-gray-400">Click for incidents and maintenance</p>
    </div>
  );
}

export function ServiceNode({ data, selected }: NodeProps<ServiceNodeType>) {
  const router = useRouter();
  const [showDetails, setShowDetails] = useState(false);
  const [isTooltipReady, setIsTooltipReady] = useState(false);
  const [tooltipDirection, setTooltipDirection] = useState<Position>(
    Position.Bottom
  );

  useEffect(() => {
    if (!showDetails) {
      setTooltipDirection(Position.Bottom);
      setIsTooltipReady(false);
      return;
    }

    const node = document.querySelector(".tooltip-ref");
    if (!node) return;

    const rect = node.getBoundingClientRect();
    const viewportHeight = window.innerHeight;

    if (rect.bottom + 10 > viewportHeight) {
      setTooltipDirection(Position.Top);
    } else {
      setTooltipDirection(Position.Bottom);
    }
    setIsTooltipReady(true);
  }, [showDetails]);

  const handleIncidentClick = (event: React.MouseEvent) => {
    event.stopPropagation();
    router.push(`/incidents?services=${encodeURIComponent(data.display_name)}`);
  };

  const handleAlertClick = (event: React.MouseEvent) => {
    event.stopPropagation();
    const cel = `service=="${data.display_name}"`;
    router.push(`/alerts/feed?cel=${encodeURIComponent(cel)}`);
  };

  const incidentsCount = data.incidents ?? 0;
  const alertsCount = data.alerts ?? 0;
  const badgeColor =
    incidentsCount < THRESHOLD ? "bg-orange-500" : "bg-red-500";
  const inMaintenance = Boolean(data.inMaintenance);
  const pendingMaintenance =
    Boolean(data.pendingMaintenance) && !inMaintenance;

  return (
    <>
      <div
        className={clsx(
          "flex flex-col gap-1 p-4 border-2 rounded-xl shadow-lg relative transition-colors cursor-pointer min-w-[10rem]",
          inMaintenance
            ? "bg-amber-50 border-amber-400 border-dashed"
            : pendingMaintenance
              ? "bg-orange-50 border-orange-300 border-dashed"
              : "bg-white border-gray-200",
          selected && !inMaintenance && !pendingMaintenance && "border-tremor-brand",
          selected && inMaintenance && "border-amber-600"
        )}
        onMouseEnter={() => setShowDetails(true)}
        onMouseLeave={() => setShowDetails(false)}
      >
        {inMaintenance ? (
          <span className="absolute -top-2 left-2 px-1.5 py-0.5 text-[9px] leading-none font-semibold uppercase tracking-wide rounded bg-amber-400 text-amber-950">
            Maint
          </span>
        ) : pendingMaintenance ? (
          <span className="absolute -top-2 left-2 px-1.5 py-0.5 text-[9px] leading-none font-semibold uppercase tracking-wide rounded bg-orange-200 text-orange-950">
            Pending
          </span>
        ) : null}
        <div className="flex items-center gap-2">
          <TopologyCategoryIcon
            category={data.category}
            className={clsx(
              "h-6 w-6",
              inMaintenance ? "text-amber-700" : "text-gray-600"
            )}
          />
          <strong className="text-lg">
            {data.display_name || data.service}
          </strong>
        </div>
        {incidentsCount > 0 ? (
          <span
            className={`absolute top-[-17px] right-[-20px] mt-2 mr-2 px-2 py-1 text-white text-[7px] leading-[7px] font-bold rounded-full ${badgeColor} hover:cursor-pointer`}
            onClick={handleIncidentClick}
          >
            {incidentsCount} {incidentsCount === 1 ? "incident" : "incidents"}
          </span>
        ) : alertsCount > 0 ? (
          <span
            className={`absolute top-[-17px] right-[-20px] mt-2 mr-2 px-2 py-1 text-white text-[7px] leading-[7px] font-bold rounded-full ${badgeColor} hover:cursor-pointer`}
            onClick={handleAlertClick}
          >
            {alertsCount} {alertsCount === 1 ? "alert" : "alerts"}
          </span>
        ) : (
          <></>
        )}
        <div className="flex flex-wrap gap-1">
          {data?.applications?.map((app) => {
            const color = getColorForUUID(app.id);
            return (
              <Badge key={app.id} color={color}>
                {app.name}
              </Badge>
            );
          })}
        </div>
      </div>

      <NodeToolbar
        isVisible={showDetails}
        position={tooltipDirection}
        className={clsx("tooltip-ref", !isTooltipReady && "invisible")}
      >
        <ServiceDetailsTooltip data={data} />
      </NodeToolbar>

      <>
        <Handle
          type="source"
          className={clsx(data.is_manual === true && "!opacity-100")}
          position={Position.Right}
          id="right"
        />
        <Handle
          type="target"
          className={clsx(data.is_manual === true && "!opacity-100")}
          position={Position.Left}
          id="left"
        />
      </>
    </>
  );
}
