"use client";

import { useMemo, useState } from "react";
import AddIcon from "@mui/icons-material/Add";
import { Box, Button, Paper, Stack, Typography } from "@mui/material";
import { KeepLoader, PageSubtitle, PageTitle, showErrorToast, showSuccessToast } from "@/shared/ui";
import { isApprovalPending } from "@/features/approvals";
import { useApi } from "@/shared/lib/hooks/useApi";
import { useAlertCatalog } from "@/features/catalog/alert-code";
import { useOnboardingProgress } from "../model/useOnboardingProgress";
import { buildLifecycleRows, type LifecycleRow } from "../model/lifecycleRows";
import { LifecycleTable } from "./LifecycleTable";
import { LifecycleViewDrawer } from "./LifecycleViewDrawer";
import { OnboardingWizard } from "./OnboardingWizard";

export function LifecyclePage() {
  const api = useApi();
  const {
    isLoading,
    installedProviders,
    catalog,
    rules,
    workflows,
    startNewLifecycle,
    editLifecycle,
    mutateCatalog,
    mutateRules,
  } = useOnboardingProgress();
  const { updateEntry, deleteEntry } = useAlertCatalog();
  const [mode, setMode] = useState<"list" | "wizard">("list");
  const [viewing, setViewing] = useState<LifecycleRow | null>(null);

  const rows = useMemo(
    () =>
      buildLifecycleRows({
        catalog,
        rules,
        workflows: workflows ?? [],
        installedProviders,
      }),
    [catalog, installedProviders, rules, workflows]
  );

  const openCreate = () => {
    startNewLifecycle();
    setViewing(null);
    setMode("wizard");
  };

  const openEdit = (row: LifecycleRow) => {
    editLifecycle(row.code);
    setViewing(null);
    setMode("wizard");
  };

  const closeWizard = () => {
    setMode("list");
  };

  const handleTogglePause = async (row: LifecycleRow) => {
    try {
      await updateEntry(row.entry.id, {
        code: row.entry.code,
        name: row.entry.name,
        description: row.entry.description || undefined,
        runbook_url: row.entry.runbook_url || undefined,
        keep_workflow_id: row.entry.keep_workflow_id || undefined,
        auto_run_on: row.entry.auto_run_on,
        disabled: !row.paused,
      });
      await mutateCatalog();
      showSuccessToast(
        row.paused
          ? `Resumed ${row.code}`
          : `Paused ${row.code} — catalog auto-run is off`
      );
    } catch (error) {
      showErrorToast(error, "Failed to update lifecycle");
    }
  };

  const handleDelete = async (row: LifecycleRow) => {
    if (
      !confirm(
        `Delete lifecycle "${row.name}" (${row.code})? This removes the catalog entry and its matching correlation rule. The attached workflow is kept.`
      )
    ) {
      return;
    }
    try {
      const result = await deleteEntry(row.entry.id);
      if (isApprovalPending(result)) {
        showSuccessToast("Delete submitted for approval");
        return;
      }
      if (row.correlation?.id) {
        const ruleResult = await api.delete(`/rules/${row.correlation.id}`);
        await mutateRules();
        if (isApprovalPending(ruleResult)) {
          showSuccessToast("Delete submitted for approval");
          return;
        }
      }
      await mutateCatalog();
      if (viewing?.id === row.id) {
        setViewing(null);
      }
      showSuccessToast(`Deleted ${row.code}`);
    } catch (error) {
      showErrorToast(error, "Failed to delete lifecycle");
    }
  };

  if (mode === "wizard") {
    return (
      <OnboardingWizard onClose={closeWizard} onFinish={closeWizard} />
    );
  }

  if (isLoading) {
    return <KeepLoader loadingText="Loading alert lifecycles…" />;
  }

  return (
    <Box
      sx={{ display: "flex", flexDirection: "column", height: "100%", p: 2 }}
      data-testid="lifecycle-page"
    >
      <Stack
        direction={{ xs: "column", md: "row" }}
        justifyContent="space-between"
        alignItems={{ xs: "stretch", md: "center" }}
        spacing={2}
        sx={{ mb: 2.5 }}
      >
        <Box>
          <PageTitle>Alert lifecycle</PageTitle>
          <PageSubtitle>
            Each row is one reserved <code>labels.code</code> wired from ingest
            through notification. View, edit, pause, or delete a lifecycle, or
            onboard another.
          </PageSubtitle>
        </Box>
        <Button
          color="primary"
          variant="contained"
          startIcon={<AddIcon />}
          onClick={openCreate}
          data-testid="onboard-lifecycle"
        >
          Onboard lifecycle
        </Button>
      </Stack>

      {rows.length === 0 ? (
        <Paper sx={{ flexGrow: 1, p: 4 }}>
          <Stack
            alignItems="center"
            justifyContent="center"
            spacing={2}
            sx={{ height: "100%", minHeight: 320, textAlign: "center" }}
          >
            <Typography variant="h5">No alert lifecycles yet</Typography>
            <Typography variant="body2" color="text.secondary">
              Onboard a reserved alert code to connect providers, correlation,
              a workflow, and notification.
            </Typography>
            <Button
              color="primary"
              variant="contained"
              startIcon={<AddIcon />}
              onClick={openCreate}
            >
              Onboard lifecycle
            </Button>
          </Stack>
        </Paper>
      ) : (
        <LifecycleTable
          rows={rows}
          onView={setViewing}
          onEdit={openEdit}
          onTogglePause={handleTogglePause}
          onDelete={handleDelete}
        />
      )}

      <LifecycleViewDrawer
        row={viewing}
        isOpen={Boolean(viewing)}
        onClose={() => setViewing(null)}
        onEdit={openEdit}
      />
    </Box>
  );
}
