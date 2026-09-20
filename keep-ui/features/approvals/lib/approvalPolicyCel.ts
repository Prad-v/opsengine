import {
  formatQuery,
  type DefaultRuleGroupType,
  type RuleGroupType,
  type RuleType,
} from "react-querybuilder";
import { parseCEL } from "react-querybuilder/parseCEL";

export const APPROVAL_CEL_FIELDS = [
  { name: "duration_seconds", label: "duration_seconds" },
  { name: "category", label: "category" },
  { name: "service", label: "service" },
  { name: "resource_type", label: "resource_type" },
  { name: "resource_id", label: "resource_id" },
  { name: "action_type", label: "action_type" },
  { name: "reason", label: "reason" },
] as const;

export const DEFAULT_APPROVAL_CEL_QUERY: DefaultRuleGroupType = {
  combinator: "or",
  rules: [
    {
      combinator: "and",
      rules: [{ field: "duration_seconds", operator: ">", value: "" }],
    },
  ],
};

function isRuleComplete(rule: RuleType): boolean {
  if (!rule.field || !rule.operator) {
    return false;
  }
  if (rule.operator === "null" || rule.operator === "notNull") {
    return true;
  }
  if (rule.value === undefined || rule.value === null) {
    return false;
  }
  return String(rule.value).trim().length > 0;
}

function pruneGroup(group: RuleGroupType): RuleGroupType | null {
  const rules = (group.rules || [])
    .map((rule) => {
      if (typeof rule === "object" && "combinator" in rule) {
        return pruneGroup(rule as RuleGroupType);
      }
      if (typeof rule === "object" && "field" in rule) {
        return isRuleComplete(rule as RuleType) ? rule : null;
      }
      return null;
    })
    .filter(Boolean) as RuleGroupType["rules"];

  if (rules.length === 0) {
    return null;
  }
  return { ...group, rules };
}

/** Drop incomplete rows before formatQuery; empty means match-all. */
export function pruneApprovalCelQuery(
  query: RuleGroupType
): RuleGroupType | null {
  return pruneGroup(query);
}

export function formatApprovalCelQuery(query: RuleGroupType): string {
  const pruned = pruneApprovalCelQuery(query);
  if (!pruned) {
    return "";
  }
  return formatQuery(pruned, "cel");
}

function normalizeToOrOfAnd(query: RuleGroupType): DefaultRuleGroupType {
  if (query.combinator === "or") {
    const rules = (query.rules || []).map((rule) => {
      if (typeof rule === "object" && "combinator" in rule) {
        return rule as RuleGroupType;
      }
      return {
        combinator: "and",
        rules: [rule as RuleType],
      };
    });
    return {
      combinator: "or",
      rules:
        rules.length > 0
          ? rules
          : [
              {
                combinator: "and",
                rules: [
                  { field: "duration_seconds", operator: ">", value: "" },
                ],
              },
            ],
    };
  }

  // Single AND group → wrap under OR
  return {
    combinator: "or",
    rules: [query],
  };
}

export function parseApprovalCelToQuery(
  cel: string | null | undefined
): DefaultRuleGroupType {
  const expression = (cel || "").trim();
  if (!expression || expression === "true") {
    return JSON.parse(JSON.stringify(DEFAULT_APPROVAL_CEL_QUERY));
  }
  try {
    const parsed = parseCEL(expression) as RuleGroupType;
    return normalizeToOrOfAnd(parsed);
  } catch {
    return JSON.parse(JSON.stringify(DEFAULT_APPROVAL_CEL_QUERY));
  }
}
