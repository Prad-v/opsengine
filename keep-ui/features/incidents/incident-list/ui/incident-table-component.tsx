import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  IconButton,
  Box,
} from "@mui/material";
import clsx from "clsx";
import { flexRender, Header, Table as ReactTable } from "@tanstack/react-table";
import React, { ReactNode } from "react";
import { IncidentDto } from "@/entities/incidents/model";
import ArrowDownwardIcon from "@mui/icons-material/ArrowDownward";
import ArrowUpwardIcon from "@mui/icons-material/ArrowUpward";
import ArrowForwardIcon from "@mui/icons-material/ArrowForward";
import { getCommonPinningStylesAndClassNames } from "@/shared/ui";

interface Props {
  table: ReactTable<IncidentDto>;
}

interface SortableHeaderCellProps {
  header: Header<IncidentDto, unknown>;
  children: ReactNode;
  className?: string;
}

const SortableHeaderCell = ({
  header,
  children,
  className,
}: SortableHeaderCellProps) => {
  const { column } = header;
  const { style, className: commonClassName } =
    getCommonPinningStylesAndClassNames(column);

  const SortIcon = column.getIsSorted()
    ? column.getIsSorted() === "asc"
      ? ArrowDownwardIcon
      : ArrowUpwardIcon
    : ArrowForwardIcon;

  return (
    <TableCell
      component="th"
      className={clsx("relative group", commonClassName, className)}
      style={style}
      sx={{ fontWeight: 600, backgroundColor: "background.paper" }}
    >
      <Box sx={{ display: "flex", alignItems: "center" }}>
        {children}
        {column.getCanSort() && (
          <>
            <Box
              sx={{
                width: "1px",
                height: 20,
                mx: 1,
                bgcolor: "divider",
              }}
            />
            <IconButton
              data-testid={"sort-direction-" + column.id}
              size="small"
              onClick={(event) => {
                event.stopPropagation();
                const toggleSorting = header.column.getToggleSortingHandler();
                if (toggleSorting) toggleSorting(event);
              }}
              title={
                column.getNextSortingOrder() === "asc"
                  ? "Sort ascending"
                  : column.getNextSortingOrder() === "desc"
                    ? "Sort descending"
                    : "Clear sort"
              }
            >
              <SortIcon fontSize="inherit" />
            </IconButton>
          </>
        )}
      </Box>
    </TableCell>
  );
};

export const IncidentTableComponent = (props: Props) => {
  const { table } = props;

  return (
    <Table data-testid="incidents-table" sx={{ minWidth: "100%" }}>
      <TableHead>
        {table.getHeaderGroups().map((headerGroup, index) => (
          <TableRow key={`${headerGroup.id}-${index}`}>
            {headerGroup.headers.map((header, index) => {
              return (
                <SortableHeaderCell
                  header={header}
                  key={`${header.id}-${index}`}
                  className={header.column.columnDef.meta?.tdClassName}
                >
                  {flexRender(
                    header.column.columnDef.header,
                    header.getContext()
                  )}
                </SortableHeaderCell>
              );
            })}
          </TableRow>
        ))}
      </TableHead>
      <TableBody>
        {table.getRowModel().rows.map((row) => (
          <TableRow key={row.id}>
            {row.getVisibleCells().map((cell) => {
              const { style, className } = getCommonPinningStylesAndClassNames(
                cell.column
              );
              return (
                <TableCell
                  key={cell.id}
                  style={style}
                  className={clsx(
                    cell.column.columnDef.meta?.tdClassName,
                    className,
                    cell.column.id === "actions" ? "p-1" : ""
                  )}
                  sx={{
                    backgroundColor: "background.paper",
                    ...(cell.column.id === "actions" ? { p: 0.5 } : {}),
                  }}
                >
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </TableCell>
              );
            })}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
};

export default IncidentTableComponent;
