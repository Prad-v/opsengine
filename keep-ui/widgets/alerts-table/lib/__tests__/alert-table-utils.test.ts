import {
  DEFAULT_COLS,
  mergeDefaultColumnOrder,
  mergeDefaultColumnVisibility,
} from "../alert-table-utils";

describe("alert table default columns", () => {
  it("includes reserved code after name", () => {
    const nameIdx = DEFAULT_COLS.indexOf("name");
    expect(DEFAULT_COLS).toContain("code");
    expect(DEFAULT_COLS[nameIdx + 1]).toBe("code");
  });

  it("inserts code after name in a saved Feed order", () => {
    const merged = mergeDefaultColumnOrder([
      "severity",
      "checkbox",
      "status",
      "source",
      "name",
      "description",
      "lastReceived",
      "alertMenu",
    ]);
    expect(merged.indexOf("code")).toBe(merged.indexOf("name") + 1);
  });

  it("keeps an explicit hidden code column hidden", () => {
    const merged = mergeDefaultColumnVisibility({
      name: true,
      description: true,
      code: false,
    });
    expect(merged.code).toBe(false);
    expect(merged.name).toBe(true);
  });

  it("shows code when an older saved visibility omitted it", () => {
    const merged = mergeDefaultColumnVisibility({
      name: true,
      description: true,
    });
    expect(merged.code).toBe(true);
  });
});
