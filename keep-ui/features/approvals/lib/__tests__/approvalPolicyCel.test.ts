import {
  DEFAULT_APPROVAL_CEL_QUERY,
  formatApprovalCelQuery,
  parseApprovalCelToQuery,
  pruneApprovalCelQuery,
} from "../approvalPolicyCel";

describe("approvalPolicyCel", () => {
  it("formats a single numeric condition", () => {
    const cel = formatApprovalCelQuery({
      combinator: "or",
      rules: [
        {
          combinator: "and",
          rules: [{ field: "duration_seconds", operator: ">", value: 14400 }],
        },
      ],
    });
    expect(cel).toContain("duration_seconds");
    expect(cel).toContain("14400");
  });

  it("formats OR of AND groups like correlation", () => {
    const cel = formatApprovalCelQuery({
      combinator: "or",
      rules: [
        {
          combinator: "and",
          rules: [{ field: "duration_seconds", operator: ">", value: 14400 }],
        },
        {
          combinator: "and",
          rules: [{ field: "category", operator: "=", value: "gpu" }],
        },
      ],
    });
    expect(cel.toLowerCase()).toContain("or");
    expect(cel).toContain("duration_seconds");
    expect(cel).toContain("category");
  });

  it("returns empty CEL when conditions are incomplete (match all)", () => {
    expect(formatApprovalCelQuery(DEFAULT_APPROVAL_CEL_QUERY)).toBe("");
    expect(pruneApprovalCelQuery(DEFAULT_APPROVAL_CEL_QUERY)).toBeNull();
  });

  it("parses a CEL string back into OR-of-AND groups", () => {
    const query = parseApprovalCelToQuery(
      'duration_seconds > 14400 || category == "gpu"'
    );
    expect(query.combinator).toBe("or");
    expect(query.rules.length).toBeGreaterThanOrEqual(1);
  });

  it("treats blank / true as empty default query", () => {
    expect(parseApprovalCelToQuery("").combinator).toBe("or");
    expect(parseApprovalCelToQuery("true").combinator).toBe("or");
  });
});
