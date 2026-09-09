import {
  ExpandedState,
  createColumnHelper,
  getCoreRowModel,
  useReactTable,
  SortingState,
  getSortedRowModel,
  ColumnDef,
  Table,
} from "@tanstack/react-table";
import type {
  IncidentDto,
  PaginatedIncidentsDto,
} from "@/entities/incidents/model";
import React, { Dispatch, SetStateAction, useCallback, useState } from "react";
import IncidentTableComponent from "./incident-table-component";
import { ManualRunWorkflowModal } from "@/features/workflows/manual-run-workflow";
import { Link } from "@/components/ui";
import { MergeIncidentsModal } from "@/features/incidents/merge-incidents";
import { IncidentDropdownMenu } from "./incident-dropdown-menu";
import clsx from "clsx";
import { IncidentChangeStatusSelect } from "features/incidents/change-incident-status";
import { useIncidentActions } from "@/entities/incidents/model";
import { getIncidentName } from "@/entities/incidents/lib/utils";
import {
  DateTimeField,
  TableIndeterminateCheckbox,
  TableSeverityCell,
  UISeverity,
} from "@/shared/ui";
import { UserStatefulAvatar } from "@/entities/users/ui";
import { DynamicImageProviderIcon } from "@/components/ui";
import { GenerateReportModal } from "./incidents-report";
import { FormattedContent } from "@/shared/ui/FormattedContent/FormattedContent";
import { Pagination, PaginationState } from "@/features/filter/pagination";
import {
  Box,
  Button,
  Chip,
  Paper,
  Stack,
  Typography,
} from "@mui/material";
import AssessmentOutlinedIcon from "@mui/icons-material/AssessmentOutlined";

function SelectedRowActions({
  selectedRowIds,
  onMergeInitiated,
  onDelete,
  onGenerateReport,
}: {
  selectedRowIds: string[];
  onMergeInitiated: () => void;
  onDelete: () => void;
  onGenerateReport: () => void;
}) {
  return (
    <Stack
      direction="row"
      justifyContent="space-between"
      alignItems="center"
      sx={{ width: "100%" }}
    >
      <Button
        color="primary"
        variant="contained"
        startIcon={<AssessmentOutlinedIcon />}
        size="medium"
        onClick={onGenerateReport}
        title="Generate report for currently visible incidents"
      >
        Generate report
      </Button>

      <Stack direction="row" spacing={1} alignItems="center">
        {selectedRowIds.length ? (
          <Typography variant="body2" color="text.secondary" sx={{ px: 1 }}>
            {selectedRowIds.length} selected
          </Typography>
        ) : null}
        <Button
          color="primary"
          variant="contained"
          size="medium"
          disabled={selectedRowIds.length < 2}
          onClick={onMergeInitiated}
        >
          Merge
        </Button>
        <Button
          color="error"
          variant="contained"
          size="medium"
          disabled={!selectedRowIds.length}
          onClick={onDelete}
        >
          Delete
        </Button>
      </Stack>
    </Stack>
  );
}

const columnHelper = createColumnHelper<IncidentDto>();

interface Props {
  filterCel: string;
  incidents: PaginatedIncidentsDto;
  sorting: SortingState;
  setSorting: Dispatch<SetStateAction<any>>;
  pagination: PaginationState;
  setPagination: Dispatch<SetStateAction<any>>;
  editCallback: (rule: IncidentDto) => void;
}

export default function IncidentsTable({
  incidents: incidents,
  filterCel,
  pagination,
  setPagination,
  sorting,
  setSorting,
  editCallback,
}: Props) {
  const { bulkDeleteIncidents } = useIncidentActions();
  const [expanded, setExpanded] = useState<ExpandedState>({});

  const [isGenerateReportModalOpen, setIsGenerateReportModalOpen] =
    useState(false);
  const [runWorkflowModalIncident, setRunWorkflowModalIncident] =
    useState<IncidentDto | null>();

  const columns = [
    columnHelper.display({
      id: "severity",
      header: () => <></>,
      cell: ({ row }) => (
        <TableSeverityCell
          severity={row.original.severity as unknown as UISeverity}
        />
      ),
      size: 4,
      minSize: 4,
      maxSize: 4,
      meta: {
        tdClassName: "p-0",
        thClassName: "p-0",
      },
    }),
    columnHelper.display({
      id: "selected",
      minSize: 32,
      maxSize: 32,
      header: (context) => {
        const selectedRows = Object.entries(
          context.table.getSelectedRowModel().rowsById
        ).map(([alertId]) => {
          return alertId;
        });

        return (
          <TableIndeterminateCheckbox
            checked={context.table.getIsAllRowsSelected()}
            indeterminate={
              context.table.getIsSomeRowsSelected() && selectedRows.length > 0
            }
            onChange={context.table.getToggleAllRowsSelectedHandler()}
            onClick={(e) => e.stopPropagation()}
          />
        );
      },
      cell: (context) => (
        <TableIndeterminateCheckbox
          checked={context.row.getIsSelected()}
          indeterminate={context.row.getIsSomeSelected()}
          onChange={context.row.getToggleSelectedHandler()}
          onClick={(e) => e.stopPropagation()}
        />
      ),
    }),
    columnHelper.display({
      id: "status",
      header: "Status",
      cell: ({ row }) => (
        <IncidentChangeStatusSelect
          incidentId={row.original.id}
          value={row.original.status}
        />
      ),
    }),
    columnHelper.display({
      id: "name",
      header: "Incident",
      cell: ({ row }) => {
        const summary =
          row.original.user_summary || row.original.generated_summary;
        return (
          <div className="min-w-32 lg:min-w-64">
            <Link
              href={`/incidents/${row.original.id}/alerts`}
              className="text-pretty"
            >
              {getIncidentName(row.original)}
            </Link>
            {summary ? (
              <FormattedContent
                content={summary}
                format="html"
                plain
                className="line-clamp-2 text-sm text-gray-500"
              />
            ) : null}
          </div>
        );
      },
      meta: {
        tdClassName: "overflow-hidden",
      },
    }),
    columnHelper.accessor("alerts_count", {
      id: "alerts_count",
      header: "Alerts",
    }),
    columnHelper.display({
      id: "alert_sources",
      header: "Sources",
      cell: ({ row }) =>
        row.original.alert_sources.map((alert_source, index) => (
          <DynamicImageProviderIcon
            key={alert_source}
            className={clsx(
              "inline-block",
              index == 0
                ? ""
                : "-ml-2 bg-white border-white border-2 rounded-full"
            )}
            alt={alert_source}
            height={24}
            width={24}
            title={alert_source}
            src={`/icons/${alert_source}-icon.png`}
          />
        )),
    }),
    columnHelper.display({
      id: "services",
      header: "Involved Services",
      cell: ({ row }) => {
        const maxServices = 2;
        const notNullServices = row.original.services.filter(
          (service) => service !== "null"
        );
        return (
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5, alignItems: "baseline" }}>
            {notNullServices
              .map((service) => (
                <Chip key={service} label={service} size="small" />
              ))
              .slice(0, maxServices)}
            {notNullServices.length > maxServices ? (
              <Typography variant="body2" component="span">
                and{" "}
                <Link href={`/incidents/${row.original.id}/alerts`}>
                  {notNullServices.length - maxServices} more
                </Link>
              </Typography>
            ) : null}
          </Box>
        );
      },
    }),
    columnHelper.display({
      id: "assignee",
      header: "Assignee",
      cell: ({ row }) => (
        <UserStatefulAvatar email={row.original.assignee} size="xs" />
      ),
    }),
    columnHelper.accessor("creation_time", {
      id: "creation_time",
      header: "Created At",
      cell: ({ row }) => <DateTimeField date={row.original.creation_time} />,
    }),
    columnHelper.display({
      id: "actions",
      header: "",
      cell: ({ row }) => (
        <div className="flex justify-end">
          <IncidentDropdownMenu
            incident={row.original}
            handleEdit={editCallback}
            handleRunWorkflow={() => setRunWorkflowModalIncident(row.original)}
          />
        </div>
      ),
    }),
  ] as ColumnDef<IncidentDto>[];

  const table: Table<IncidentDto> = useReactTable({
    columns,
    data: incidents.items,
    state: {
      expanded,
      sorting,
      columnPinning: {
        left: ["severity", "selected"],
        right: ["actions"],
      },
    },
    getRowId: (row) => row.id,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    rowCount: incidents.count,
    onExpandedChange: setExpanded,
    onSortingChange: (value) => {
      if (typeof value === "function") {
        setSorting(value);
      }
    },
    getSortedRowModel: getSortedRowModel(),
    enableSorting: true,
    enableMultiSort: false,
    manualSorting: true,
  });

  const selectedRowIds = Object.entries(
    table.getSelectedRowModel().rowsById
  ).reduce<string[]>((acc, [alertId]) => {
    return acc.concat(alertId);
  }, []);

  type MergeOptions = {
    incidents: IncidentDto[];
  };

  const [mergeOptions, setMergeOptions] = useState<MergeOptions | null>(null);
  const handleMergeInitiated = useCallback(() => {
    const selectedIncidents = selectedRowIds.map(
      (incidentId) =>
        incidents.items.find((incident) => incident.id === incidentId)!
    );

    setMergeOptions({
      incidents: selectedIncidents,
    });
  }, [incidents.items, selectedRowIds]);

  const handleDeleteMultiple = useCallback(() => {
    if (selectedRowIds.length === 0) {
      return;
    }

    const isConfirmed = confirm(
      `Are you sure you want to delete ${selectedRowIds.length} incidents? This action cannot be undone.`
    );

    if (!isConfirmed) {
      return;
    }

    bulkDeleteIncidents(selectedRowIds, true);
  }, [bulkDeleteIncidents, selectedRowIds]);

  const generateReport = useCallback(
    () => setIsGenerateReportModalOpen(true),
    [setIsGenerateReportModalOpen]
  );

  return (
    <>
      <SelectedRowActions
        selectedRowIds={selectedRowIds}
        onMergeInitiated={handleMergeInitiated}
        onDelete={handleDeleteMultiple}
        onGenerateReport={generateReport}
      />
      {incidents.items.length > 0 ? (
        <Paper sx={{ p: 0, overflow: "hidden" }}>
          <IncidentTableComponent table={table} />
        </Paper>
      ) : (
        <Paper sx={{ flexGrow: 1, p: 4 }}>
          <Stack
            alignItems="center"
            justifyContent="center"
            spacing={1.5}
            sx={{ height: "100%", textAlign: "center" }}
          >
            <Typography variant="h5">No Incidents Matching Filters</Typography>
            <Typography variant="body2" color="text.secondary">
              Try changing the filters
            </Typography>
          </Stack>
        </Paper>
      )}
      <Box sx={{ mt: 2, mb: 4 }}>
        <Pagination
          totalCount={incidents.count}
          isRefreshing={false}
          isRefreshAllowed={false}
          state={pagination}
          onStateChange={setPagination}
        />
      </Box>
      <ManualRunWorkflowModal
        incident={runWorkflowModalIncident}
        onClose={() => setRunWorkflowModalIncident(null)}
      />
      {mergeOptions && (
        <MergeIncidentsModal
          incidents={mergeOptions.incidents}
          handleClose={() => setMergeOptions(null)}
          onSuccess={() => table.resetRowSelection()}
        />
      )}
      {isGenerateReportModalOpen && (
        <GenerateReportModal
          filterCel={filterCel}
          onClose={() => setIsGenerateReportModalOpen(false)}
        />
      )}
    </>
  );
}
