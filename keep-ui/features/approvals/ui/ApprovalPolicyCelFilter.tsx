"use client";

import { useEffect, useState } from "react";
import {
  Button,
  SearchSelect,
  SearchSelectItem,
  Select,
  SelectItem,
  Text,
  TextInput,
} from "@tremor/react";
import { QuestionMarkCircleIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { get } from "lodash";
import QueryBuilder, {
  defaultOperators,
  type Field as QueryField,
  type QueryActions,
  type QueryRuleGroupProps,
  type RuleGroupType,
  type RuleGroupTypeAny,
  type RuleType,
} from "react-querybuilder";
import {
  APPROVAL_CEL_FIELDS,
  parseApprovalCelToQuery,
} from "../lib/approvalPolicyCel";

const DEFAULT_OPERATORS = defaultOperators.filter((operator) =>
  [
    "=",
    "!=",
    ">",
    "<",
    ">=",
    "<=",
    "contains",
    "beginsWith",
    "endsWith",
    "doesNotContain",
    "doesNotBeginWith",
    "doesNotEndWith",
    "null",
    "notNull",
    "in",
    "notIn",
  ].includes(operator.name)
);

const OPERATORS_FORCE_TYPE_CAST: Record<string, string> = {
  ">=": "number",
  "<=": "number",
  "<": "number",
  ">": "number",
};

const BASE_FIELDS: QueryField[] = APPROVAL_CEL_FIELDS.map((field) => ({
  name: field.name,
  label: field.label,
  datatype: "text",
}));

type FieldRowProps = {
  ruleField: RuleType<string, string, any, string>;
  availableFields: QueryField[];
  onRemoveFieldClick: () => void;
  onFieldChange: (
    prop: Parameters<QueryActions["onPropChange"]>[0],
    value: unknown
  ) => void;
  isInputRemovalDisabled: boolean;
};

function FieldRow({
  ruleField,
  availableFields,
  onRemoveFieldClick,
  onFieldChange,
  isInputRemovalDisabled,
}: FieldRowProps) {
  const [fields, setFields] = useState<QueryField[]>(availableFields);
  const [searchValue, setSearchValue] = useState("");
  const [isValueEnabled, setIsValueEnabled] = useState(
    ruleField.operator !== "null" && ruleField.operator !== "notNull"
  );

  useEffect(() => {
    setFields(availableFields);
  }, [availableFields]);

  const onValueChange = (selectedValue: string) => {
    const next = selectedValue || "";
    if (searchValue.length) {
      const exists = fields.some(
        ({ name }) => name.toLowerCase().trim() === next.toLowerCase().trim()
      );
      if (!exists) {
        setSearchValue("");
        setFields((prev) => [
          ...prev,
          { name: next, label: next, datatype: "text" },
        ]);
      }
    }
    onFieldChange("field", next);
  };

  const onOperatorSelect = (selectedValue: string) => {
    onFieldChange("operator", selectedValue);
    setIsValueEnabled(
      selectedValue !== "null" && selectedValue !== "notNull"
    );
  };

  const castValueToOperationType = (value: string) => {
    const castTo = get(
      OPERATORS_FORCE_TYPE_CAST,
      ruleField.operator,
      "text"
    );
    return castTo === "number" ? Number(value) : value;
  };

  return (
    <div className="flex items-start gap-2">
      <div className="flex-1 min-w-0 grid grid-cols-3 gap-2">
        <SearchSelect
          defaultValue={ruleField.field}
          onValueChange={onValueChange}
          onSearchValueChange={setSearchValue}
          enableClear={false}
        >
          {fields.map((field) => (
            <SearchSelectItem key={field.name} value={field.name}>
              {field.label}
            </SearchSelectItem>
          ))}
          {searchValue.trim() ? (
            <SearchSelectItem value={searchValue}>{searchValue}</SearchSelectItem>
          ) : null}
        </SearchSelect>
        <Select
          className="[&_ul]:max-h-96"
          defaultValue={ruleField.operator}
          onValueChange={onOperatorSelect}
        >
          {DEFAULT_OPERATORS.map((operator) => (
            <SelectItem key={operator.name} value={operator.name}>
              {operator.label}
            </SelectItem>
          ))}
        </Select>
        {isValueEnabled ? (
          <TextInput
            onValueChange={(newValue) =>
              onFieldChange("value", castValueToOperationType(newValue))
            }
            defaultValue={ruleField.value}
            placeholder="Type..."
          />
        ) : null}
      </div>
      <Button
        className="mt-2"
        onClick={onRemoveFieldClick}
        size="lg"
        color="red"
        icon={XMarkIcon}
        variant="light"
        type="button"
        disabled={isInputRemovalDisabled}
        title={
          isInputRemovalDisabled
            ? "Keep at least one condition, or clear values to match all"
            : undefined
        }
      />
    </div>
  );
}

type RuleFieldsProps = {
  rule: RuleGroupType<RuleType<string, string, any, string>, string>;
  onRuleAdd: QueryActions["onRuleAdd"];
  onRuleRemove: QueryActions["onRuleRemove"];
  onPropChange: QueryActions["onPropChange"];
  groupIndex: number;
  query: RuleGroupTypeAny;
  groupsLength: number;
};

function RuleFields({
  rule,
  onRuleAdd,
  onRuleRemove,
  onPropChange,
  groupIndex,
  query,
  groupsLength,
}: RuleFieldsProps) {
  const { rules: ruleFields } = rule;

  const selectedFields = ruleFields.reduce<string[]>(
    (acc, ruleField) =>
      "field" in ruleField ? acc.concat(ruleField.field) : acc,
    []
  );

  const availableFields = BASE_FIELDS.filter(
    ({ name }) => !selectedFields.includes(name)
  );

  const onAddRuleFieldClick = () => {
    const next = availableFields.at(0) || {
      name: "category",
      label: "category",
    };
    onRuleAdd({ field: next.name, operator: "=", value: "" }, [groupIndex], query);
  };

  const onRemoveRuleFieldClick = (removedRuleFieldIndex: number) => {
    if (groupsLength === 1 && ruleFields.length < 2) {
      // Keep one empty row so the form still has a slot; clear via value.
      onPropChange("value", "", [groupIndex, removedRuleFieldIndex]);
      return;
    }
    if (ruleFields.length === 1) {
      onRuleRemove([groupIndex]);
      return;
    }
    onRuleRemove([groupIndex, removedRuleFieldIndex]);
  };

  const onRemoveGroupClick = () => {
    if (groupsLength > 1) {
      onRuleRemove([groupIndex]);
    }
  };

  const onFieldChange = (
    prop: Parameters<QueryActions["onPropChange"]>[0],
    value: unknown,
    ruleFieldIndex: number
  ) => {
    onPropChange(prop, value, [groupIndex, ruleFieldIndex]);
  };

  return (
    <div className="bg-gray-100 px-4 py-3 rounded space-y-2">
      {ruleFields.map((ruleField, ruleFieldIndex) => {
        if (!("field" in ruleField)) {
          return null;
        }
        const isInputRemovalDisabled =
          groupsLength === 1 && ruleFields.length < 2;
        return (
          <div key={ruleField.id || ruleFieldIndex}>
            <div className="mb-2">{ruleFieldIndex > 0 ? "AND" : ""}</div>
            <FieldRow
              ruleField={ruleField}
              availableFields={availableFields.concat({
                label: ruleField.field,
                name: ruleField.field,
              })}
              onRemoveFieldClick={() =>
                onRemoveRuleFieldClick(ruleFieldIndex)
              }
              onFieldChange={(prop, value) =>
                onFieldChange(prop, value, ruleFieldIndex)
              }
              isInputRemovalDisabled={isInputRemovalDisabled}
            />
          </div>
        );
      })}
      <div className="flex justify-between items-center">
        <Button
          onClick={onAddRuleFieldClick}
          type="button"
          variant="light"
          color="orange"
        >
          Add condition
        </Button>
        <Button
          type="button"
          variant="light"
          color="red"
          disabled={groupsLength <= 1}
          title={
            groupsLength <= 1 ? "You must have at least one group" : undefined
          }
          onClick={onRemoveGroupClick}
        >
          Remove group
        </Button>
      </div>
    </div>
  );
}

function RuleGroup({ actions, ruleGroup }: QueryRuleGroupProps) {
  const { onRuleAdd, onGroupAdd, onRuleRemove, onPropChange } = actions;
  const { rules } = ruleGroup;

  const onAddGroupClick = () => {
    onGroupAdd(
      {
        combinator: "and",
        rules: [{ field: "category", operator: "=", value: "" }],
      },
      []
    );
  };

  return (
    <div className="space-y-2">
      {rules.map((rule, groupIndex) =>
        typeof rule === "object" && "combinator" in rule ? (
          <div key={rule.id || groupIndex}>
            <div className="mb-2">{groupIndex > 0 ? "OR" : ""}</div>
            <RuleFields
              rule={
                rule as RuleGroupType<
                  RuleType<string, string, any, string>,
                  string
                >
              }
              groupIndex={groupIndex}
              onRuleAdd={onRuleAdd}
              onRuleRemove={onRuleRemove}
              onPropChange={onPropChange}
              query={ruleGroup}
              groupsLength={rules.length}
            />
          </div>
        ) : null
      )}
      <Button
        className="mt-3"
        onClick={onAddGroupClick}
        type="button"
        variant="light"
        color="orange"
      >
        Add filter
      </Button>
    </div>
  );
}

interface ApprovalPolicyCelFilterProps {
  value: string;
  onChange: (query: RuleGroupType) => void;
  query: RuleGroupType;
}

export function ApprovalPolicyCelFilter({
  onChange,
  query,
}: ApprovalPolicyCelFilterProps) {
  return (
    <div>
      <div className="flex justify-between items-center mb-2">
        <Text className="font-medium text-tremor-content-strong">
          Match when (optional)
        </Text>
        <Button
          className="cursor-default"
          type="button"
          tooltip="Conditions in a group are AND. Groups are OR. Leave values empty to match all actions of this type. Fields come from the gated payload (duration_seconds, category, service, resource_type, ...)."
          icon={QuestionMarkCircleIcon}
          size="xs"
          variant="light"
          color="slate"
        />
      </div>
      <QueryBuilder
        query={query}
        onQueryChange={onChange}
        addRuleToNewGroups
        controlElements={{
          ruleGroup: RuleGroup,
        }}
      />
      <Text className="mt-2 text-xs text-tremor-content">
        Empty conditions match all. Example: duration_seconds &gt; 14400 OR
        category = gpu
      </Text>
    </div>
  );
}

export function useApprovalPolicyCelQuery(initialCel?: string | null) {
  const [query, setQuery] = useState<RuleGroupType>(() =>
    parseApprovalCelToQuery(initialCel)
  );

  useEffect(() => {
    setQuery(parseApprovalCelToQuery(initialCel));
  }, [initialCel]);

  return { query, setQuery };
}
