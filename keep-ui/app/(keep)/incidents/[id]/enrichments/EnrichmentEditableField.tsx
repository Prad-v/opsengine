import { useRouter } from "next/navigation";
import React, { useState } from "react";
import { xor } from "lodash";
import { Badge, Icon, TextInput } from "@tremor/react";
import { Button } from "@/components/ui";
import { FiSave, FiTrash2, FiX } from "react-icons/fi";
import { MdModeEdit } from "react-icons/md";

interface EnrichmentEditableFieldProps {
  name?: string;
  value: string | string[] | unknown;
  onUpdate: (fieldName: string, newValue: string | string[]) => void;
  onDelete?: (fieldName: string) => void;
  children?: React.ReactNode;
}

function formatEnrichmentItem(item: unknown): string {
  if (item == null) {
    return "";
  }
  if (typeof item === "string") {
    return item;
  }
  if (typeof item === "number" || typeof item === "boolean") {
    return String(item);
  }
  try {
    return JSON.stringify(item);
  } catch {
    return String(item);
  }
}

function toDisplayString(value: unknown): string {
  if (Array.isArray(value)) {
    return value.map(formatEnrichmentItem).join(", ");
  }
  return formatEnrichmentItem(value);
}

export const EnrichmentEditableField = ({
  name,
  value,
  onUpdate,
  onDelete,
  children,
}: EnrichmentEditableFieldProps) => {
  const router = useRouter();

  const [editMode, setEditMode] = useState(false);
  const [stringedValue, setStringedValue] = useState(toDisplayString(value));
  const [fieldName, setFieldName] = useState<string>(name || "");
  const [fieldNameError, setFieldNameError] = useState<boolean>(false);
  const [valueError, setValueError] = useState<boolean>(false);

  const handleSave = async () => {
    const newValue = Array.isArray(value)
      ? stringedValue.split(",").map((s) => s.trim())
      : stringedValue.toString().trim();

    if (Array.isArray(newValue) && xor(value, newValue).length === 0) {
      return;
    } else if (value == newValue) {
      return;
    }

    onUpdate(fieldName, newValue);
    setEditMode(false);

    // reset if this is add form
    resetForm();
  };

  const handleUnenrich = async () => {
    if (onDelete) {
      onDelete(fieldName);
    }
    setEditMode(false);
  };

  const handleCancel = () => {
    // Reset value
    setEditMode(false);
    resetForm();
  };

  const resetForm = () => {
    setStringedValue(toDisplayString(value));
    setFieldName(name || "");
  };

  const filterBy = (key: string, value: string) => {
    router.push(
      `/alerts/feed?cel=${key}%3D%3D${encodeURIComponent(`"${value}"`)}`
    );
  };

  const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFieldNameError(e.target.value === "");
    setFieldName(e.target.value);
  };

  const handleValueChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setValueError(e.target.value === "");
    setStringedValue(e.target.value);
  };

  if (editMode) {
    return (
      <div className="flex items-center flex-wrap gap-2.5 z-50">
        {!name && (
          <TextInput
            value={fieldName}
            error={fieldNameError}
            onChange={handleNameChange}
            placeholder="Add name"
          />
        )}
        <TextInput
          value={stringedValue}
          error={valueError}
          onChange={handleValueChange}
          placeholder="Add value"
        />
        <Button
          className="leading-none p-2 rounded-md"
          variant="secondary"
          disabled={!(fieldName && stringedValue)}
          tooltip="Save"
          icon={() => (
            <Icon icon={FiSave} className={`w-4 h-4 text-orange-500`} />
          )}
          onClick={handleSave}
        />
        <Button
          className="leading-none p-2 rounded-md"
          variant="destructive"
          tooltip="Cancel"
          icon={FiX}
          onClick={handleCancel}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1 relative">
      {name ? (
        <div className="flex flex-wrap gap-1 group items-center">
          {children
            ? children
            : value != null && toDisplayString(value).length > 0
              ? !Array.isArray(value)
                ? formatEnrichmentItem(value)
                : value.map((item: unknown, index: number) => {
                    const label = formatEnrichmentItem(item);
                    return (
                      <Badge
                        key={`${label}-${index}`}
                        color="orange"
                        size="sm"
                        className="cursor-pointer"
                        onClick={() => filterBy(fieldName, label)}
                      >
                        {label}
                      </Badge>
                    );
                  })
              : `No data for ${name}`}

          <Button
            variant="light"
            className="text-gray-500 leading-none p-2 rounded-md prevent-row-click hover:bg-slate-200 [&>[role='tooltip']]:z-50 transition-opacity duration-100 opacity-0 group-hover:opacity-100"
            tooltip="Edit"
            onClick={() => setEditMode(true)}
            icon={() => (
              <Icon icon={MdModeEdit} className={`w-4 h-4 text-orange-500`} />
            )}
          />

          {onDelete && (
            <Button
              variant="light"
              className="text-gray-500 leading-none p-2 rounded-md prevent-row-click hover:bg-slate-200 [&>[role='tooltip']]:z-50 transition-opacity duration-100 opacity-0 group-hover:opacity-100"
              tooltip="Un-enrich"
              onClick={handleUnenrich}
              icon={() => (
                <Icon icon={FiTrash2} className={`w-4 h-4 text-red-500`} />
              )}
            />
          )}
        </div>
      ) : (
        <div
          className="flex gap-2 items-center cursor-pointer"
          onClick={() => setEditMode(true)}
        >
          <Badge>+</Badge> Add new field
        </div>
      )}
    </div>
  );
};
