import { getConfig } from "../getConfig";

describe("getConfig ALERT_SIDEBAR_FIELDS", () => {
  const original = process.env.ALERT_SIDEBAR_FIELDS;

  afterEach(() => {
    if (original === undefined) {
      delete process.env.ALERT_SIDEBAR_FIELDS;
    } else {
      process.env.ALERT_SIDEBAR_FIELDS = original;
    }
  });

  it("includes reserved code after source by default", () => {
    delete process.env.ALERT_SIDEBAR_FIELDS;
    const fields = getConfig().ALERT_SIDEBAR_FIELDS;
    expect(fields).toContain("code");
    expect(fields.indexOf("code")).toBe(fields.indexOf("source") + 1);
  });

  it("parses a comma-separated override", () => {
    process.env.ALERT_SIDEBAR_FIELDS = "service, source, fingerprint";
    expect(getConfig().ALERT_SIDEBAR_FIELDS).toEqual([
      "service",
      "source",
      "fingerprint",
    ]);
  });
});
