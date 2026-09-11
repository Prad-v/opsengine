import { Button, Tooltip } from "@mui/material";
import { useState } from "react";
import { AlertDto } from "@/entities/alerts/model";
import { PlusIcon, RocketIcon } from "@radix-ui/react-icons";
import { toast } from "react-toastify";
import { useRouter, useSearchParams } from "next/navigation";
import { SilencedDoorbellNotification } from "@/components/icons";
import { AlertAssociateIncidentModal } from "@/features/alerts/alert-associate-to-incident";
import { CreateIncidentWithAIModal } from "@/features/alerts/alert-create-incident-ai";
import { useApi } from "@/shared/lib/hooks/useApi";
import { Table } from "@tanstack/react-table";

import { useRevalidateMultiple } from "@/shared/lib/state-utils";
import { useAISettings } from "@/features/settings/ai";
import { XMarkIcon } from "@heroicons/react/24/outline";
import { ChevronDoubleRightIcon } from "@heroicons/react/24/solid";
import { AlertChangeStatusModal } from "@/features/alerts/alert-change-status/ui/alert-change-status-modal";

interface Props {
  selectedAlertsFingerprints: string[];
  table: Table<AlertDto>;
  clearRowSelection: () => void;
  setDismissModalAlert?: (alert: AlertDto[] | null) => void;
  mutateAlerts?: () => void;
  setIsIncidentSelectorOpen: (open: boolean) => void;
  isIncidentSelectorOpen: boolean;
  setIsCreateIncidentWithAIOpen: (open: boolean) => void;
  isCreateIncidentWithAIOpen: boolean;
}

export default function AlertActions({
  selectedAlertsFingerprints,
  table,
  clearRowSelection,
  setDismissModalAlert,
  mutateAlerts,
  setIsIncidentSelectorOpen,
  isIncidentSelectorOpen,
  setIsCreateIncidentWithAIOpen,
  isCreateIncidentWithAIOpen,
}: Props) {
  const router = useRouter();
  const api = useApi();
  const { isAIEnabled } = useAISettings();
  const revalidateMultiple = useRevalidateMultiple();
  const presetsMutator = () => revalidateMultiple(["/preset"]);
  const [modalAlert, setModalAlert] = useState<AlertDto | AlertDto[] | null>(null);

  // TODO: refactor
  const searchParams = useSearchParams();
  const createIncidentsFromLastAlerts = searchParams.get(
    "createIncidentsFromLastAlerts"
  );

  const selectedAlerts = table
    .getSelectedRowModel()
    .rows.map((row) => row.original);

  async function addOrUpdatePreset() {
    const newPresetName = prompt("Enter new preset name");
    if (newPresetName) {
      const distinctAlertNames = Array.from(
        new Set(selectedAlerts.map((alert) => alert.name))
      );
      const formattedCel = distinctAlertNames.reduce(
        (accumulator, currentValue, currentIndex) => {
          return (
            accumulator +
            (currentIndex > 0 ? " || " : "") +
            `name == "${currentValue}"`
          );
        },
        ""
      );
      const options = [{ value: formattedCel, label: "CEL" }];
      try {
        await api.post(`/preset`, {
          name: newPresetName,
          options: options,
        });
        toast(`Preset ${newPresetName} created!`, {
          position: "top-left",
          type: "success",
        });
        presetsMutator();
        clearRowSelection();
        router.replace(`/alerts/${newPresetName}`);
      } catch (error) {
        toast(`Error creating preset ${newPresetName}`, {
          position: "top-left",
          type: "error",
        });
      }
    }
  }

  const showIncidentSelector = () => {
    setIsIncidentSelectorOpen(true);
  };
  const hideIncidentSelector = () => {
    setIsIncidentSelectorOpen(false);
  };

  const showCreateIncidentWithAI = () => {
    setIsCreateIncidentWithAIOpen(true);
  };
  const hideCreateIncidentWithAI = () => {
    setIsCreateIncidentWithAIOpen(false);
  };

  const handleSuccessfulAlertsAssociation = () => {
    hideIncidentSelector();
    clearRowSelection();
    if (mutateAlerts) {
      mutateAlerts();
    }
  };

  return (
    <div className="w-full flex gap-2.5 justify-end items-center">
      <Button
        size="small"
        color="inherit"
        variant="outlined"
        startIcon={<XMarkIcon className="h-4 w-4" />}
        title="Clear Selection"
        onClick={clearRowSelection}
      >
        Clear Selection
      </Button>
      <Button
        size="small"
        color="info"
        variant="contained"
        startIcon={<ChevronDoubleRightIcon className="h-4 w-4" />}
        title="Resolve"
        onClick={() => {
          setModalAlert(selectedAlerts);
        }}
      >
        Change status of {selectedAlertsFingerprints.length} alert(s)
      </Button>
      {modalAlert && (
        <AlertChangeStatusModal
          alert={modalAlert}
          presetName="resolve"
          handleClose={() => {
            setModalAlert(null);
            clearRowSelection();
          }}
        />
      )}
      <Button
        size="small"
        color="error"
        variant="contained"
        startIcon={<SilencedDoorbellNotification />}
        title="Delete"
        onClick={() => {
          setDismissModalAlert?.(selectedAlerts);
          clearRowSelection();
        }}
      >
        Dismiss {selectedAlertsFingerprints.length} alert(s)
      </Button>
      <Tooltip title="Save current filter as a view">
        <span>
          <Button
            size="small"
            color="primary"
            variant="contained"
            startIcon={<PlusIcon className="h-4 w-4" />}
            onClick={async () => await addOrUpdatePreset()}
          >
            Create Preset
          </Button>
        </span>
      </Tooltip>
      <Tooltip title="Associate events with incident">
        <span>
          <Button
            size="small"
            color="primary"
            variant="contained"
            startIcon={<PlusIcon className="h-4 w-4" />}
            onClick={showIncidentSelector}
          >
            Associate with incident
          </Button>
        </span>
      </Tooltip>
      <Tooltip
        title={
          isAIEnabled ? "Create incidents with AI" : "AI is not configured"
        }
      >
        <span>
          <Button
            size="small"
            color="primary"
            variant="contained"
            startIcon={<RocketIcon className="h-4 w-4" />}
            onClick={showCreateIncidentWithAI}
            disabled={!isAIEnabled}
          >
            Create incidents with AI
          </Button>
        </span>
      </Tooltip>
      <AlertAssociateIncidentModal
        isOpen={isIncidentSelectorOpen}
        alerts={selectedAlerts}
        handleSuccess={handleSuccessfulAlertsAssociation}
        handleClose={hideIncidentSelector}
      />
      <CreateIncidentWithAIModal
        isOpen={isCreateIncidentWithAIOpen}
        alerts={selectedAlerts}
        handleClose={hideCreateIncidentWithAI}
      />
    </div>
  );
}
