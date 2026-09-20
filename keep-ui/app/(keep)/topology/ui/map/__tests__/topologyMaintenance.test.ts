import {
  celLiterals,
  findActiveMaintenanceRule,
  findPendingNodeMaintenance,
  maintenanceCelForService,
  maintenanceRuleCoversService,
  topologyMaintenanceRuleName,
} from "../topologyMaintenance";

describe("maintenanceCelForService", () => {
  it("scopes GPU, host, and rack nodes to location labels", () => {
    expect(maintenanceCelForService("gpu-node-a03-gpu0", "gpu")).toBe(
      'labels.gpu_id == "gpu-node-a03-gpu0"'
    );
    expect(maintenanceCelForService("gpu-node-a03", "host")).toBe(
      'labels.host == "gpu-node-a03" || service == "gpu-node-a03"'
    );
    expect(maintenanceCelForService("rack-12", "rack")).toBe(
      'labels.rack == "rack-12"'
    );
    expect(maintenanceCelForService("gpu-inference", "service")).toBe(
      'service == "gpu-inference"'
    );
  });

  it("escapes quotes in the service name", () => {
    expect(maintenanceCelForService('node"x', "host")).toContain('\\"');
  });
});

describe("maintenanceRuleCoversService", () => {
  const now = new Date("2026-09-14T12:00:00Z");

  it("matches an exact CEL string literal, not a prefix of another node", () => {
    const gpuRule = {
      cel_query: 'labels.gpu_id == "gpu-node-a03-gpu0"',
      enabled: true,
      status: "active" as const,
      start_time: new Date("2026-09-14T11:00:00Z"),
      end_time: new Date("2026-09-14T16:00:00Z"),
    };
    expect(
      maintenanceRuleCoversService(gpuRule, "gpu-node-a03-gpu0", now)
    ).toBe(true);
    expect(maintenanceRuleCoversService(gpuRule, "gpu-node-a03", now)).toBe(
      false
    );
  });

  it("ignores expired and disabled rules", () => {
    expect(
      maintenanceRuleCoversService(
        {
          cel_query: 'labels.host == "gpu-node-a03"',
          enabled: false,
          start_time: new Date("2026-09-14T11:00:00Z"),
          end_time: new Date("2026-09-14T16:00:00Z"),
        },
        "gpu-node-a03",
        now
      )
    ).toBe(false);
    expect(
      maintenanceRuleCoversService(
        {
          cel_query: 'labels.host == "gpu-node-a03"',
          enabled: true,
          start_time: new Date("2026-09-14T11:00:00Z"),
          end_time: new Date("2026-09-14T11:30:00Z"),
        },
        "gpu-node-a03",
        now
      )
    ).toBe(false);
  });

  it("finds the active rule for a node", () => {
    const rule = {
      id: 9,
      cel_query: 'labels.rack == "rack-12"',
      enabled: true,
      status: "active" as const,
      start_time: new Date("2026-09-14T11:00:00Z"),
      end_time: new Date("2026-09-14T16:00:00Z"),
    };
    expect(findActiveMaintenanceRule([rule], "rack-12", now)?.id).toBe(9);
    expect(findActiveMaintenanceRule([rule], "rack-11", now)).toBeUndefined();
  });
});

describe("celLiterals and naming", () => {
  it("extracts quoted CEL values", () => {
    expect(
      celLiterals('labels.host == "gpu-node-a03" || service == "gpu-node-a03"')
    ).toEqual(["gpu-node-a03", "gpu-node-a03"]);
  });

  it("names the rule for the Maintenance Windows page", () => {
    expect(topologyMaintenanceRuleName("gpu-node-a03", "RMA")).toBe(
      "Topology: gpu-node-a03 (RMA)"
    );
  });
});

describe("findPendingNodeMaintenance", () => {
  it("matches a pending node_maintenance request by resource_id", () => {
    const pending = {
      action_type: "node_maintenance",
      status: "pending",
      resource_id: "gpu-node-a03",
      context: {},
      payload: {},
    };
    expect(findPendingNodeMaintenance([pending], "gpu-node-a03")).toBe(pending);
    expect(
      findPendingNodeMaintenance([pending], "gpu-node-a01")
    ).toBeUndefined();
  });
});
