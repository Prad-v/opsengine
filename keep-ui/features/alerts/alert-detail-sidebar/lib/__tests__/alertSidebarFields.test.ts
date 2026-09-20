import { AlertDto } from "@/entities/alerts/model";
import {
  DEFAULT_ALERT_SIDEBAR_FIELDS,
  getAlertCode,
  getEnabledFields,
  mergeDefaultSidebarFields,
} from "../alertSidebarFieldLogic";

function alertWith(overrides: Partial<AlertDto>): AlertDto {
  return {
    fingerprint: "fp",
    name: "NvidiaGpuUnavailable",
    ...overrides,
  } as AlertDto;
}

describe("alert sidebar reserved code", () => {
  it("places code after source in the default field list", () => {
    expect(DEFAULT_ALERT_SIDEBAR_FIELDS).toContain("code");
    expect(
      DEFAULT_ALERT_SIDEBAR_FIELDS.indexOf("code")
    ).toBe(DEFAULT_ALERT_SIDEBAR_FIELDS.indexOf("source") + 1);
  });

  it("reads alert.code then labels.code", () => {
    expect(getAlertCode(alertWith({ code: "NVIDIA_GPU_UNAVAILABLE" }))).toBe(
      "NVIDIA_GPU_UNAVAILABLE"
    );
    expect(
      getAlertCode(alertWith({ labels: { code: "HIGH_CPU" } }))
    ).toBe("HIGH_CPU");
    expect(getAlertCode(alertWith({}))).toBeUndefined();
  });

  it("treats a missing code as empty", () => {
    expect(getAlertCode(alertWith({ code: "", labels: {} }))).toBeUndefined();
  });

  it("inserts code after source on older ALERT_SIDEBAR_FIELDS lists", () => {
    const merged = mergeDefaultSidebarFields([
      "service",
      "source",
      "description",
      "fingerprint",
    ]);
    expect(merged.indexOf("code")).toBe(merged.indexOf("source") + 1);
  });

  it("keeps an explicit code position", () => {
    const merged = mergeDefaultSidebarFields(["code", "service", "source"]);
    expect(merged[0]).toBe("code");
    expect(merged.filter((field) => field === "code")).toHaveLength(1);
  });

  it("uses the full default list when config is empty", () => {
    expect(mergeDefaultSidebarFields([])).toEqual(DEFAULT_ALERT_SIDEBAR_FIELDS);
  });

  it("enables the reserved code field from the default list", () => {
    expect(getEnabledFields(DEFAULT_ALERT_SIDEBAR_FIELDS)).toContain("code");
  });
});
