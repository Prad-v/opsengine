"use client";

import type { ReactNode } from "react";
import {
  Chip,
  IconButton,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from "@mui/material";
import VisibilityOutlinedIcon from "@mui/icons-material/VisibilityOutlined";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
import PauseCircleOutlineIcon from "@mui/icons-material/PauseCircleOutline";
import PlayCircleOutlineIcon from "@mui/icons-material/PlayCircleOutline";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import { Link } from "@/components/ui";
import { DateTimeField } from "@/shared/ui";
import type { LifecycleRow } from "../model/lifecycleRows";

interface LifecycleTableProps {
  rows: LifecycleRow[];
  onView: (row: LifecycleRow) => void;
  onEdit: (row: LifecycleRow) => void;
  onTogglePause: (row: LifecycleRow) => void;
  onDelete: (row: LifecycleRow) => void;
}

function dash(value: ReactNode) {
  return value ? (
    value
  ) : (
    <Typography variant="body2" color="text.secondary">
      —
    </Typography>
  );
}

export function LifecycleTable({
  rows,
  onView,
  onEdit,
  onTogglePause,
  onDelete,
}: LifecycleTableProps) {
  return (
    <Paper
      data-testid="lifecycle-table"
      sx={{ flexGrow: 1, overflow: "auto" }}
    >
      <Table sx={{ minWidth: "100%" }}>
        <TableHead>
          <TableRow>
            <TableCell sx={{ fontWeight: 600 }}>Code</TableCell>
            <TableCell sx={{ fontWeight: 600 }}>Name</TableCell>
            <TableCell sx={{ fontWeight: 600 }}>Status</TableCell>
            <TableCell sx={{ fontWeight: 600 }}>Correlation</TableCell>
            <TableCell sx={{ fontWeight: 600 }}>Workflow</TableCell>
            <TableCell sx={{ fontWeight: 600 }}>Auto-run</TableCell>
            <TableCell sx={{ fontWeight: 600 }}>Notification</TableCell>
            <TableCell sx={{ fontWeight: 600 }}>Progress</TableCell>
            <TableCell sx={{ fontWeight: 600 }}>Updated</TableCell>
            <TableCell sx={{ fontWeight: 600 }} align="right">
              Actions
            </TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row) => (
            <TableRow
              key={row.id}
              hover
              sx={{ cursor: "pointer" }}
              onClick={() => onView(row)}
              data-testid={`lifecycle-row-${row.code}`}
            >
              <TableCell>
                <code className="text-sm">{row.code}</code>
              </TableCell>
              <TableCell>
                <Typography variant="body2" fontWeight={600}>
                  {row.name}
                </Typography>
                {row.description ? (
                  <Typography variant="caption" color="text.secondary">
                    {row.description}
                  </Typography>
                ) : null}
              </TableCell>
              <TableCell>
                <Chip
                  size="small"
                  label={row.paused ? "Paused" : "Active"}
                  color={row.paused ? "default" : "success"}
                />
              </TableCell>
              <TableCell>
                {row.correlation
                  ? dash(
                      <Link
                        href={`/rules?id=${row.correlation.id}`}
                        onClick={(event) => event.stopPropagation()}
                      >
                        {row.correlation.name}
                      </Link>
                    )
                  : dash(null)}
              </TableCell>
              <TableCell>
                {row.workflow
                  ? dash(
                      <Link
                        href={`/workflows/${row.workflow.id}`}
                        onClick={(event) => event.stopPropagation()}
                      >
                        {row.workflow.name}
                      </Link>
                    )
                  : dash(null)}
              </TableCell>
              <TableCell>
                <Chip size="small" label={row.autoRunOn} variant="outlined" />
              </TableCell>
              <TableCell>
                <Chip
                  size="small"
                  label={row.notification ? "Wired" : "Not wired"}
                  color={row.notification ? "success" : "default"}
                  variant={row.notification ? "filled" : "outlined"}
                />
              </TableCell>
              <TableCell>
                <Typography variant="body2">
                  {row.completedCount}/{row.totalCount}
                </Typography>
              </TableCell>
              <TableCell>
                {row.updatedAt ? (
                  <DateTimeField date={row.updatedAt as unknown as Date} />
                ) : (
                  dash(null)
                )}
              </TableCell>
              <TableCell
                onClick={(event) => event.stopPropagation()}
                sx={{ p: 0.5, whiteSpace: "nowrap" }}
                align="right"
              >
                <Stack direction="row" justifyContent="flex-end" spacing={0.25}>
                  <Tooltip title="View">
                    <IconButton
                      size="small"
                      aria-label={`View ${row.code}`}
                      onClick={() => onView(row)}
                    >
                      <VisibilityOutlinedIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Edit">
                    <IconButton
                      size="small"
                      aria-label={`Edit ${row.code}`}
                      onClick={() => onEdit(row)}
                    >
                      <EditOutlinedIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title={row.paused ? "Resume" : "Pause"}>
                    <IconButton
                      size="small"
                      aria-label={
                        row.paused ? `Resume ${row.code}` : `Pause ${row.code}`
                      }
                      onClick={() => onTogglePause(row)}
                    >
                      {row.paused ? (
                        <PlayCircleOutlineIcon fontSize="small" />
                      ) : (
                        <PauseCircleOutlineIcon fontSize="small" />
                      )}
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Delete">
                    <IconButton
                      size="small"
                      aria-label={`Delete ${row.code}`}
                      onClick={() => onDelete(row)}
                    >
                      <DeleteOutlineIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </Stack>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Paper>
  );
}
