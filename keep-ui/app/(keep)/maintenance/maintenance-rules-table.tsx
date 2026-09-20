import {
  Badge,
  Button,
  Icon,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@tremor/react";
import {
  DisplayColumnDef,
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { MdRemoveCircle, MdModeEdit } from "react-icons/md";
import { toast } from "react-toastify";
import { MaintenanceRule } from "./model";
import { IoCheckmark } from "react-icons/io5";
import { HiMiniXMark } from "react-icons/hi2";
import { showErrorToast } from "@/shared/ui";
import { useMaintenanceRules } from "@/utils/hooks/useMaintenanceRules";
import {
  parseMaintenanceDate,
  remainingLabel,
  ruleLifecycle,
} from "./lib/maintenanceRuleUtils";

const columnHelper = createColumnHelper<MaintenanceRule>();

interface Props {
  maintenanceRules: MaintenanceRule[];
  editCallback: (rule: MaintenanceRule) => void;
}

const lifecycleColor: Record<string, "green" | "blue" | "gray" | "red"> = {
  active: "green",
  upcoming: "blue",
  expired: "gray",
  disabled: "red",
};

export default function MaintenanceRulesTable({
  maintenanceRules,
  editCallback,
}: Props) {
  const { deleteRule, endNow, extend } = useMaintenanceRules();

  const formatDate = (value?: Date | string) => {
    const parsed = parseMaintenanceDate(value ?? null);
    return parsed ? parsed.toLocaleString() : "N/A";
  };

  const columns = [
    columnHelper.display({
      id: "actions",
      header: "",
      cell: (context) => {
        const rule = context.row.original;
        const status = ruleLifecycle(rule);
        return (
          <div className="space-x-1 flex flex-row items-center justify-center">
            <Button
              color="orange"
              size="xs"
              variant="secondary"
              icon={MdModeEdit}
              tooltip="Edit"
              onClick={(e: any) => {
                e.preventDefault();
                e.stopPropagation();
                editCallback(rule);
              }}
            />
            {status === "active" ? (
              <>
                <Button
                  color="gray"
                  size="xs"
                  variant="secondary"
                  onClick={async (e: any) => {
                    e.preventDefault();
                    e.stopPropagation();
                    if (
                      !confirm("End this maintenance window now?")
                    ) {
                      return;
                    }
                    try {
                      await endNow(rule.id!);
                      toast.success("Maintenance window ended");
                    } catch (error) {
                      showErrorToast(error, "Failed to end maintenance window");
                    }
                  }}
                >
                  End now
                </Button>
                <Button
                  color="gray"
                  size="xs"
                  variant="secondary"
                  onClick={async (e: any) => {
                    e.preventDefault();
                    e.stopPropagation();
                    try {
                      await extend(rule.id!, 1800);
                      toast.success("Extended by 30 minutes");
                    } catch (error) {
                      showErrorToast(error, "Failed to extend maintenance window");
                    }
                  }}
                >
                  +30m
                </Button>
              </>
            ) : null}
            <Button
              color="red"
              size="xs"
              variant="secondary"
              icon={MdRemoveCircle}
              tooltip="Delete"
              onClick={async (e: any) => {
                e.preventDefault();
                e.stopPropagation();
                if (
                  !confirm("Are you sure you want to delete this maintenance rule?")
                ) {
                  return;
                }
                try {
                  await deleteRule(rule.id!);
                  toast.success("Maintenance rule deleted successfully");
                } catch (error) {
                  showErrorToast(error, "Failed to delete maintenance rule");
                }
              }}
            />
          </div>
        );
      },
    }),
    columnHelper.display({
      id: "name",
      header: "Name",
      cell: ({ row }) => row.original.name,
    }),
    columnHelper.display({
      id: "CEL",
      header: "CEL",
      cell: (context) => (
        <span className="font-mono text-xs">{context.row.original.cel_query}</span>
      ),
    }),
    columnHelper.display({
      id: "start_time",
      header: "Starts",
      cell: (context) => formatDate(context.row.original.start_time),
    }),
    columnHelper.display({
      id: "end_time",
      header: "Ends",
      cell: (context) => formatDate(context.row.original.end_time),
    }),
    columnHelper.display({
      id: "mode",
      header: "Mode",
      cell: (context) =>
        context.row.original.suppress ? "Suppressed" : "Hidden",
    }),
    columnHelper.display({
      id: "lifecycle",
      header: "Status",
      cell: (context) => {
        const status = ruleLifecycle(context.row.original);
        const remaining =
          status === "active"
            ? remainingLabel(context.row.original.end_time)
            : null;
        return (
          <div className="flex items-center gap-2">
            <Badge color={lifecycleColor[status]} size="xs">
              {status}
            </Badge>
            {remaining ? (
              <span className="text-xs text-tremor-content">{remaining}</span>
            ) : null}
          </div>
        );
      },
    }),
    columnHelper.display({
      id: "enabled",
      header: "Enabled",
      cell: (context) => (
        <div>
          {context.row.original.enabled ? (
            <Icon icon={IoCheckmark} size="md" color="orange" />
          ) : (
            <Icon icon={HiMiniXMark} size="md" color="orange" />
          )}
        </div>
      ),
    }),
  ] as DisplayColumnDef<MaintenanceRule>[];

  const table = useReactTable({
    getRowId: (row) => row.id.toString(),
    columns,
    data: maintenanceRules,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <Table>
      <TableHead>
        {table.getHeaderGroups().map((headerGroup) => (
          <TableRow
            className="border-b border-tremor-border dark:border-dark-tremor-border"
            key={headerGroup.id}
          >
            {headerGroup.headers.map((header) => (
              <TableHeaderCell
                className="text-tremor-content-strong dark:text-dark-tremor-content-strong"
                key={header.id}
              >
                {flexRender(
                  header.column.columnDef.header,
                  header.getContext()
                )}
              </TableHeaderCell>
            ))}
          </TableRow>
        ))}
      </TableHead>
      <TableBody>
        {table.getRowModel().rows.map((row) => (
          <TableRow
            className="even:bg-tremor-background-muted even:dark:bg-dark-tremor-background-muted hover:bg-slate-100"
            key={row.id}
          >
            {row.getVisibleCells().map((cell) => (
              <TableCell key={cell.id}>
                {flexRender(cell.column.columnDef.cell, cell.getContext())}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
