"use client";

import React, { useMemo, useState } from "react";
import type {
  IncidentDto,
  PaginatedIncidentsDto,
} from "@/entities/incidents/model";
import { CreateOrUpdateIncidentForm } from "features/incidents/create-or-update-incident";
import IncidentsTable from "./incidents-table";
import { IncidentListPlaceholder } from "./incident-list-placeholder";
import Modal from "@/components/ui/Modal";
import PredictedIncidentsTable from "@/app/(keep)/incidents/predicted-incidents-table";
import { SortingState } from "@tanstack/react-table";
import { IncidentListError } from "@/features/incidents/incident-list/ui/incident-list-error";
import { InitialFacetsData } from "@/features/filter/api";
import { FacetsPanelServerSide } from "@/features/filter/facet-panel-server-side";
import {
  KeepLoader,
  PageSubtitle,
  PageTitle,
  SeverityBorderIcon,
  UISeverity,
} from "@/shared/ui";
import { BellIcon, BellSlashIcon } from "@heroicons/react/24/outline";
import { UserStatefulAvatar } from "@/entities/users/ui";
import { getStatusIcon, getStatusColor } from "@/shared/lib/status-utils";
import { useUser } from "@/entities/users/model/useUser";
import {
  reverseSeverityMapping,
  severityMapping,
} from "@/entities/alerts/model";
import {
  IncidentsNotFoundForFiltersPlaceholder,
  IncidentsNotFoundPlaceholder,
} from "./incidents-not-found";
import { v4 as uuidV4 } from "uuid";
import { FacetsConfig } from "@/features/filter/models";
import {
  DEFAULT_INCIDENTS_PAGE_SIZE,
  DEFAULT_INCIDENTS_SORTING,
  DEFAULT_INCIDENTS_CHECKED_OPTIONS,
} from "@/entities/incidents/model/models";
import { DynamicImageProviderIcon } from "@/components/ui";
import { useIncidentsTableData } from "./useIncidentsTableData";
import EnhancedDateRangePickerV2, {
  AllTimeFrame,
} from "@/components/ui/DateRangePickerV2";
import { useTimeframeState } from "@/components/ui/useTimeframeState";
import { PaginationState } from "@/features/filter/pagination";
import {
  Box,
  Button as MuiButton,
  Chip,
  Paper,
  Stack,
  Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";

const STATUS_COLOR_CLASS: Record<string, string> = {
  red: "text-red-500",
  green: "text-green-500",
  gray: "text-gray-500",
  purple: "text-purple-500",
};

const AssigneeLabel = ({ email }: { email: string }) => {
  const user = useUser(email);
  return user ? user.name : email;
};

export function IncidentList({
  initialFacetsData,
}: {
  initialData?: PaginatedIncidentsDto;
  initialFacetsData?: InitialFacetsData;
}) {
  const [incidentsPagination, setIncidentsPagination] =
    useState<PaginationState>({
      limit: DEFAULT_INCIDENTS_PAGE_SIZE,
      offset: 0,
    });

  const [incidentsSorting, setIncidentsSorting] = useState<SortingState>([
    DEFAULT_INCIDENTS_SORTING,
  ]);

  const [filterCel, setFilterCel] = useState<string | null>(null);

  const [dateRange, setDateRange] = useTimeframeState({
    enableQueryParams: true,
    defaultTimeframe: {
      type: "all-time",
      isPaused: false,
    } as AllTimeFrame,
  });

  const {
    isEmptyState,
    incidents,
    incidentsLoading,
    incidentsError,
    predictedIncidents,
    isPredictedLoading,
    facetsCel,
  } = useIncidentsTableData({
    candidate: null,
    predicted: null,
    limit: incidentsPagination.limit,
    offset: incidentsPagination.offset,
    sorting: incidentsSorting[0],
    filterCel: filterCel,
    timeFrame: dateRange,
  });

  const [incidentToEdit, setIncidentToEdit] = useState<IncidentDto | null>(
    null
  );

  const [clearFiltersToken, setClearFiltersToken] = useState<string | null>(
    null
  );
  const [filterRevalidationToken, setFilterRevalidationToken] = useState<
    string | undefined
  >(undefined);
  const [isFormOpen, setIsFormOpen] = useState<boolean>(false);

  const handleCloseForm = () => {
    setIsFormOpen(false);
    setIncidentToEdit(null);
  };

  const handleStartEdit = (incident: IncidentDto) => {
    setIncidentToEdit(incident);
    setIsFormOpen(true);
  };

  const handleFinishEdit = () => {
    setIncidentToEdit(null);
    setIsFormOpen(false);
  };

  const facetsConfig: FacetsConfig = useMemo(() => {
    return {
      ["Severity"]: {
        canHitEmptyState: false,
        renderOptionLabel: (facetOption) => {
          const label =
            severityMapping[Number(facetOption.display_name)] ||
            facetOption.display_name;
          return <span className="capitalize">{label}</span>;
        },
        renderOptionIcon: (facetOption) => (
          <SeverityBorderIcon
            severity={
              (severityMapping[Number(facetOption.display_name)] ||
                facetOption.display_name) as UISeverity
            }
          />
        ),
        sortCallback: (facetOption) =>
          reverseSeverityMapping[facetOption.value] || 100, // if status is not in the mapping, it should be at the end
      },
      ["Status"]: {
        checkedByDefaultOptionValues: DEFAULT_INCIDENTS_CHECKED_OPTIONS,
        renderOptionIcon: (facetOption) => {
          const StatusIcon = getStatusIcon(facetOption.display_name);
          const color = getStatusColor(facetOption.display_name);
          return (
            <StatusIcon
              className={`h-4 w-4 ${STATUS_COLOR_CLASS[color] ?? "text-gray-500"}`}
            />
          );
        },
      },
      ["Source"]: {
        renderOptionIcon: (facetOption) => {
          if (facetOption.display_name === "None") {
            return;
          }

          return (
            <DynamicImageProviderIcon
              className="inline-block"
              alt={facetOption.display_name}
              height={16}
              width={16}
              title={facetOption.display_name}
              src={`/icons/${facetOption.display_name}-icon.png`}
            />
          );
        },
      },
      ["Assignee"]: {
        renderOptionIcon: (facetOption) => (
          <UserStatefulAvatar email={facetOption.display_name} size="xs" />
        ),
        renderOptionLabel: (facetOption) => {
          if (!facetOption.display_name) {
            return "Not assigned";
          }
          return <AssigneeLabel email={facetOption.display_name} />;
        },
      },
      ["Dismissed"]: {
        renderOptionLabel: (facetOption) =>
          facetOption.display_name === "true" ? "Dismissed" : "Not dismissed",
        renderOptionIcon: (facetOption) => {
          const Icon =
            facetOption.display_name === "true" ? BellSlashIcon : BellIcon;
          return <Icon className="h-4 w-4 text-gray-600" />;
        },
      },
      ["Linked incident"]: {
        sortCallback: (facetOption) =>
          facetOption.display_name == "1" ||
          facetOption.display_name.toLocaleLowerCase() == "true"
            ? 1
            : 0,
        renderOptionLabel: (facetOption) =>
          facetOption.display_name == "1" ||
          facetOption.display_name.toLocaleLowerCase() == "true"
            ? "Yes"
            : "No",
      },
    };
  }, []);

  const handleClearFilters = () => {
    setDateRange({
      type: "all-time",
      isPaused: false,
    } as AllTimeFrame);
    setIncidentsPagination({
      limit: DEFAULT_INCIDENTS_PAGE_SIZE,
      offset: 0,
    });
    setClearFiltersToken(uuidV4());
  };

  function renderIncidents() {
    if (incidentsLoading) {
      return <KeepLoader></KeepLoader>;
    }

    if (incidents && incidents.items.length > 0) {
      return (
        <IncidentsTable
          filterCel={facetsCel}
          incidents={incidents}
          pagination={incidentsPagination}
          setPagination={setIncidentsPagination}
          sorting={incidentsSorting}
          setSorting={setIncidentsSorting}
          editCallback={handleStartEdit}
        />
      );
    }

    if (isEmptyState) {
      return <IncidentsNotFoundPlaceholder />;
    }

    if (facetsCel && incidents?.items.length === 0) {
      return (
        <IncidentsNotFoundForFiltersPlaceholder
          onClearFilters={handleClearFilters}
        />
      );
    }

    // This is shown on the cold page load. FIXME
    return (
      <Paper sx={{ flexGrow: 1, p: 2 }}>
        <IncidentListPlaceholder setIsFormOpen={setIsFormOpen} />
      </Paper>
    );
  }

  const renderDateTimePicker = () => {
    return (
      <Box sx={{ display: "flex", justifyContent: "flex-end" }}>
        {dateRange && (
          <EnhancedDateRangePickerV2
            timeFrame={dateRange}
            setTimeFrame={setDateRange}
            timeframeRefreshInterval={20000}
            hasPlay={true}
            pausedByDefault={false}
            hasRewind={false}
            hasForward={false}
            hasZoomOut={false}
            enableYearNavigation
          />
        )}
      </Box>
    );
  };

  return (
    <Box sx={{ display: "flex", height: "100%", width: "100%" }}>
      <Box sx={{ flexGrow: 1, minWidth: 0 }}>
        {!isPredictedLoading &&
        predictedIncidents &&
        predictedIncidents.items.length > 0 ? (
          <Paper sx={{ mt: 5, mb: 5, flexGrow: 1, p: 2 }}>
            <Typography variant="h6">Incident Predictions</Typography>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
              <Typography variant="body2" color="text.secondary">
                Possible problems predicted by Keep AI & Correlation Rules
              </Typography>
              <Chip label="Beta" color="warning" size="small" />
            </Stack>
            <PredictedIncidentsTable
              incidents={predictedIncidents}
              editCallback={handleStartEdit}
            />
          </Paper>
        ) : null}

        <Stack spacing={2.5} sx={{ height: "100%" }}>
          <Stack
            direction="row"
            justifyContent="space-between"
            alignItems="center"
          >
            <Box>
              <PageTitle>Incidents</PageTitle>
              <PageSubtitle>Group alerts into incidents</PageSubtitle>
            </Box>

            <Stack direction="row" spacing={1} alignItems="center">
              {renderDateTimePicker()}
              <MuiButton
                color="primary"
                variant="contained"
                size="medium"
                startIcon={<AddIcon />}
                onClick={() => setIsFormOpen(true)}
              >
                Create Incident
              </MuiButton>
            </Stack>
          </Stack>
          <Box>
            {incidentsError ? (
              <IncidentListError incidentError={incidentsError} />
            ) : null}
            {incidentsError ? null : (
              <Stack direction="row" spacing={2.5}>
                <FacetsPanelServerSide
                  className="mt-14"
                  entityName={"incidents"}
                  facetsConfig={facetsConfig}
                  facetOptionsCel={facetsCel}
                  usePropertyPathsSuggestions={true}
                  clearFiltersToken={clearFiltersToken}
                  initialFacetsData={initialFacetsData}
                  onCelChange={setFilterCel}
                  revalidationToken={filterRevalidationToken}
                />
                <Stack spacing={2.5} sx={{ flex: 1, minWidth: 0 }}>
                  {renderIncidents()}
                </Stack>
              </Stack>
            )}
          </Box>
        </Stack>
      </Box>
      <Modal
        isOpen={isFormOpen}
        onClose={handleCloseForm}
        className="w-[600px]"
        title="Add Incident"
      >
        <CreateOrUpdateIncidentForm
          incidentToEdit={incidentToEdit}
          exitCallback={handleFinishEdit}
        />
      </Modal>
    </Box>
  );
}
