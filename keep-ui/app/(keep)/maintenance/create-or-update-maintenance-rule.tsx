import {
  TextInput,
  Textarea,
  Divider,
  Subtitle,
  Text,
  Button,
  Switch,
  NumberInput,
  Select,
  SelectItem,
  MultiSelect,
  MultiSelectItem,
  Callout,
} from "@tremor/react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { toast } from "react-toastify";
import { MaintenanceRule } from "./model";
import { useMaintenanceRules } from "@/utils/hooks/useMaintenanceRules";
import { isApprovalPending } from "@/features/approvals";
import { AlertsRulesBuilder } from "@/features/presets/presets-manager";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import { useRouter } from "next/navigation";
import { showErrorToast } from "@/shared/ui";
import { Status } from "@/entities/alerts/model";
import { capitalize } from "@/utils/helpers";
import {
  CEL_SHORTCUTS,
  durationFromSeconds,
  durationToSeconds,
} from "./lib/maintenanceRuleUtils";
import type { MaintenanceDurationUnit } from "./model";
import type { MaintenancePreviewResult } from "./model";

interface Props {
  maintenanceToEdit: MaintenanceRule | null;
  editCallback: (rule: MaintenanceRule | null) => void;
}

const DEFAULT_IGNORE_STATUSES = ["resolved", "acknowledged"];

export default function CreateOrUpdateMaintenanceRule({
  maintenanceToEdit,
  editCallback,
}: Props) {
  const { createRule, updateRule, preview } = useMaintenanceRules();
  const [maintenanceName, setMaintenanceName] = useState<string>("");
  const [description, setDescription] = useState<string>("");
  const [celQuery, setCelQuery] = useState<string>("");
  const [startTime, setStartTime] = useState<Date | null>(new Date());
  const [endInterval, setEndInterval] = useState<number>(5);
  const [intervalType, setIntervalType] =
    useState<MaintenanceDurationUnit>("minutes");
  const [enabled, setEnabled] = useState<boolean>(true);
  const [suppress, setSuppress] = useState<boolean>(true);
  const [ignoreStatuses, setIgnoreStatuses] = useState<string[]>(
    DEFAULT_IGNORE_STATUSES
  );
  const [priority, setPriority] = useState<number>(0);
  const [previewResult, setPreviewResult] =
    useState<MaintenancePreviewResult | null>(null);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const editMode = maintenanceToEdit !== null;
  const router = useRouter();
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  useEffect(() => {
    if (maintenanceToEdit) {
      setMaintenanceName(maintenanceToEdit.name);
      setDescription(maintenanceToEdit.description ?? "");
      setCelQuery(maintenanceToEdit.cel_query);
      setStartTime(new Date(maintenanceToEdit.start_time));
      setSuppress(maintenanceToEdit.suppress);
      setEnabled(maintenanceToEdit.enabled);
      setIgnoreStatuses(maintenanceToEdit.ignore_statuses ?? []);
      setPriority(maintenanceToEdit.priority ?? 0);
      if (maintenanceToEdit.duration_seconds) {
        const parsed = durationFromSeconds(
          maintenanceToEdit.duration_seconds
        );
        setEndInterval(parsed.value);
        setIntervalType(parsed.unit);
      }
    }
  }, [maintenanceToEdit]);

  const clearForm = () => {
    setMaintenanceName("");
    setDescription("");
    setCelQuery("");
    setStartTime(new Date());
    setEndInterval(5);
    setIntervalType("minutes");
    setSuppress(true);
    setEnabled(true);
    setIgnoreStatuses(DEFAULT_IGNORE_STATUSES);
    setPriority(0);
    setPreviewResult(null);
    router.replace("/maintenance");
  };

  const durationSeconds = durationToSeconds(endInterval, intervalType);
  const endAt = useMemo(() => {
    if (!startTime) {
      return null;
    }
    return new Date(startTime.getTime() + durationSeconds * 1000);
  }, [startTime, durationSeconds]);

  useEffect(() => {
    if (!celQuery.trim()) {
      setPreviewResult(null);
      return;
    }
    let cancelled = false;
    const timer = setTimeout(async () => {
      setIsPreviewing(true);
      try {
        const result = await preview(celQuery.trim());
        if (!cancelled) {
          setPreviewResult(result);
        }
      } catch {
        if (!cancelled) {
          setPreviewResult(null);
        }
      } finally {
        if (!cancelled) {
          setIsPreviewing(false);
        }
      }
    }, 400);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [celQuery, preview]);

  const addMaintenanceRule = async (e: FormEvent) => {
    e.preventDefault();
    try {
      const created = await createRule({
        name: maintenanceName,
        description: description,
        cel_query: celQuery,
        start_time: startTime!.toISOString(),
        duration_seconds: durationSeconds,
        suppress: suppress,
        enabled: enabled,
        ignore_statuses: ignoreStatuses,
        priority,
      });
      clearForm();
      toast.success(
        isApprovalPending(created)
          ? "Sent for approval"
          : "Maintenance rule created successfully"
      );
    } catch (error) {
      showErrorToast(error, "Failed to create maintenance rule");
    }
  };

  const updateMaintenanceRule = async (e: FormEvent) => {
    e.preventDefault();
    if (!maintenanceToEdit?.id) {
      showErrorToast(new Error("No maintenance rule selected for update"));
      return;
    }
    try {
      await updateRule(maintenanceToEdit.id, {
        name: maintenanceName,
        description: description,
        cel_query: celQuery,
        start_time: startTime!.toISOString(),
        duration_seconds: durationSeconds,
        suppress: suppress,
        enabled: enabled,
        ignore_statuses: ignoreStatuses,
        priority,
      });
      exitEditMode();
      toast.success("Maintenance rule updated successfully");
    } catch (error) {
      showErrorToast(error, "Failed to update maintenance rule");
    }
  };

  const exitEditMode = () => {
    editCallback(null);
    clearForm();
  };

  const missingFields: string[] = [];
  if (!maintenanceName.trim()) {
    missingFields.push("Name is required");
  }
  if (!celQuery.trim()) {
    missingFields.push('CEL filter is required (use true to match all)');
  }
  if (!startTime) {
    missingFields.push("Start time is required");
  }
  const submitEnabled = missingFields.length === 0;

  return (
    <form
      className="py-2"
      onSubmit={editMode ? updateMaintenanceRule : addMaintenanceRule}
    >
      <Subtitle>Maintenance Rule Metadata</Subtitle>
      <div className="mt-2.5">
        <Text>
          Name<span className="text-red-500 text-xs">*</span>
        </Text>
        <TextInput
          placeholder="Maintenance Name"
          required={true}
          value={maintenanceName}
          onValueChange={setMaintenanceName}
        />
      </div>
      <div className="mt-2.5">
        <Text>Description</Text>
        <Textarea
          placeholder="Maintenance Description"
          value={description}
          onValueChange={setDescription}
        />
      </div>
      <div className="mt-2.5">
        <Text>
          CEL filter<span className="text-red-500 text-xs">*</span>
        </Text>
        <div className="flex flex-wrap gap-1 mb-2">
          {CEL_SHORTCUTS.map((shortcut) => (
            <Button
              key={shortcut.label}
              type="button"
              size="xs"
              variant="secondary"
              color="gray"
              onClick={() => setCelQuery(shortcut.cel)}
            >
              {shortcut.label}
            </Button>
          ))}
        </div>
        <AlertsRulesBuilder
          defaultQuery={celQuery}
          updateOutputCEL={setCelQuery}
          showSave={false}
          showSqlImport={false}
        />
        <Text className="text-xs mt-1">
          {isPreviewing
            ? "Checking recent alerts…"
            : previewResult
              ? `${previewResult.count} alert${previewResult.count === 1 ? "" : "s"} in the last 24h would match`
              : "Preview runs against alerts from the last 24 hours"}
        </Text>
      </div>

      <div className="mt-2.5">
        <Text>Do not suppress these statuses</Text>
        <Text className="text-xs mb-1">
          Resolved and Acknowledged still flow so incidents can close.
        </Text>
        <MultiSelect value={ignoreStatuses} onValueChange={setIgnoreStatuses}>
          {Object.values(Status).map((value) => {
            return (
              <MultiSelectItem key={value} value={value}>
                {capitalize(value)}
              </MultiSelectItem>
            );
          })}
        </MultiSelect>
      </div>
      <div className="mt-2.5">
        <Text>
          Start At<span className="text-red-500 text-xs">*</span>
        </Text>
        <DatePicker
          onChange={(date) => setStartTime(date)}
          showTimeSelect
          selected={startTime}
          timeFormat="p"
          timeIntervals={15}
          minDate={editMode ? undefined : new Date()}
          timeCaption="Time"
          dateFormat="MMMM d, yyyy h:mm aa"
          className="w-full border rounded-md px-2 py-1.5 text-sm"
        />
        <Text className="text-xs mt-1">Timezone: {timeZone}</Text>
      </div>
      <div className="mt-2.5">
        <Text>
          End After<span className="text-red-500 text-xs">*</span>
        </Text>
        <div className="flex gap-2">
          <NumberInput
            value={endInterval}
            onValueChange={setEndInterval}
            min={1}
          />
          <Select
            value={intervalType}
            onValueChange={(value) =>
              setIntervalType(value as MaintenanceDurationUnit)
            }
          >
            <SelectItem value="minutes">Minutes</SelectItem>
            <SelectItem value="hours">Hours</SelectItem>
            <SelectItem value="days">Days</SelectItem>
          </Select>
        </div>
        {startTime && endAt ? (
          <Text className="text-xs mt-1">
            Starts {startTime.toLocaleString()} · Ends {endAt.toLocaleString()}{" "}
            ({timeZone})
          </Text>
        ) : null}
      </div>
      <div className="mt-2.5">
        <Text>Priority</Text>
        <Text className="text-xs mb-1">
          Higher priority wins when rules overlap.
        </Text>
        <NumberInput
          value={priority}
          onValueChange={setPriority}
          min={0}
        />
      </div>
      <div className="mt-3 flex flex-col gap-2">
        <Text>Alert handling</Text>
        <label className="flex items-start gap-2 cursor-pointer">
          <input
            type="radio"
            name="maintenance-suppress"
            className="mt-1"
            checked={suppress}
            onChange={() => setSuppress(true)}
          />
          <span>
            <span className="text-sm font-medium">Show in feed as suppressed</span>
            <Text className="text-xs">
              Matching alerts are saved with suppressed status. Workflows and
              incidents are skipped while suppressed.
            </Text>
          </span>
        </label>
        <label className="flex items-start gap-2 cursor-pointer">
          <input
            type="radio"
            name="maintenance-suppress"
            className="mt-1"
            checked={!suppress}
            onChange={() => setSuppress(false)}
          />
          <span>
            <span className="text-sm font-medium">
              Hide from feed (do not persist)
            </span>
            <Text className="text-xs">
              Matching alerts are not saved. Use only when you want no record
              of the noise.
            </Text>
          </span>
        </label>
        {!suppress ? (
          <Callout title="Alerts will not be saved" color="red">
            Matching alerts will not be persisted. Workflows and incidents will
            not run.
          </Callout>
        ) : null}
      </div>
      <div className="flex items-center space-x-3 w-[300px] justify-between mt-2.5">
        <label
          htmlFor="enabledSwitch"
          className="text-tremor-default text-tremor-content dark:text-dark-tremor-content"
        >
          Whether this rule is enabled or not
        </label>
        <Switch id="enabledSwitch" checked={enabled} onChange={setEnabled} />
      </div>
      {!submitEnabled ? (
        <Text className="text-xs text-red-500 mt-2">
          {missingFields.join(". ")}
        </Text>
      ) : null}
      <Divider />
      <div className={"space-x-1 flex flex-row justify-end items-center"}>
        {editMode ? (
          <Button
            color="orange"
            size="xs"
            variant="secondary"
            onClick={exitEditMode}
          >
            Cancel
          </Button>
        ) : null}
        <Button
          disabled={!submitEnabled}
          color="orange"
          size="xs"
          type="submit"
        >
          {editMode ? "Update" : "Create"}
        </Button>
      </div>
    </form>
  );
}
