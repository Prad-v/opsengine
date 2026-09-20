import {
  durationFromSeconds,
  durationToSeconds,
  remainingLabel,
  ruleLifecycle,
} from "../maintenanceRuleUtils";

describe("durationFromSeconds", () => {
  it("loads a two-day window as days, not thousands of minutes", () => {
    expect(durationFromSeconds(172800)).toEqual({ value: 2, unit: "days" });
  });

  it("loads exact hours", () => {
    expect(durationFromSeconds(7200)).toEqual({ value: 2, unit: "hours" });
  });

  it("falls back to minutes", () => {
    expect(durationFromSeconds(300)).toEqual({ value: 5, unit: "minutes" });
  });
});

describe("durationToSeconds", () => {
  it("converts units back to seconds", () => {
    expect(durationToSeconds(2, "days")).toBe(172800);
    expect(durationToSeconds(2, "hours")).toBe(7200);
    expect(durationToSeconds(5, "minutes")).toBe(300);
  });
});

describe("ruleLifecycle", () => {
  const now = new Date("2026-09-14T12:00:00.000Z");

  it("uses the API status when present", () => {
    expect(
      ruleLifecycle(
        {
          enabled: true,
          start_time: now,
          end_time: now,
          status: "upcoming",
        },
        now
      )
    ).toBe("upcoming");
  });

  it("returns disabled when the rule is off", () => {
    expect(
      ruleLifecycle(
        {
          enabled: false,
          start_time: new Date("2026-09-14T11:00:00.000Z"),
          end_time: new Date("2026-09-14T13:00:00.000Z"),
        },
        now
      )
    ).toBe("disabled");
  });

  it("returns upcoming before start", () => {
    expect(
      ruleLifecycle(
        {
          enabled: true,
          start_time: new Date("2026-09-14T13:00:00.000Z"),
          end_time: new Date("2026-09-14T14:00:00.000Z"),
        },
        now
      )
    ).toBe("upcoming");
  });

  it("returns expired after end", () => {
    expect(
      ruleLifecycle(
        {
          enabled: true,
          start_time: new Date("2026-09-14T10:00:00.000Z"),
          end_time: new Date("2026-09-14T11:00:00.000Z"),
        },
        now
      )
    ).toBe("expired");
  });

  it("returns active inside the window", () => {
    expect(
      ruleLifecycle(
        {
          enabled: true,
          start_time: new Date("2026-09-14T11:00:00.000Z"),
          end_time: new Date("2026-09-14T13:00:00.000Z"),
        },
        now
      )
    ).toBe("active");
  });
});

describe("remainingLabel", () => {
  it("shows minutes left for an active window", () => {
    expect(
      remainingLabel(
        "2026-09-14T12:05:00.000Z",
        new Date("2026-09-14T12:00:00.000Z")
      )
    ).toBe("5m left");
  });
});
