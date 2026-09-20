import {
  alertMatchesTopologyService,
  incidentMatchesTopologyService,
} from "../topologyAlertMatch";

describe("alertMatchesTopologyService", () => {
  const gpuAlert = {
    service: "gpu-inference",
    labels: {
      host: "gpu-node-a03",
      rack: "rack-12",
      row: "row-a",
      datacenter: "ai-dc-1",
      region: "us-west-2",
      gpu_id: "gpu-node-a03-gpu0",
    },
  };

  it("matches the logical inference service", () => {
    expect(
      alertMatchesTopologyService(gpuAlert, { service: "gpu-inference" })
    ).toBe(true);
  });

  it("matches region / datacenter / row / rack / host / gpu labels", () => {
    expect(alertMatchesTopologyService(gpuAlert, { service: "us-west-2" })).toBe(
      true
    );
    expect(alertMatchesTopologyService(gpuAlert, { service: "ai-dc-1" })).toBe(
      true
    );
    expect(alertMatchesTopologyService(gpuAlert, { service: "row-a" })).toBe(
      true
    );
    expect(alertMatchesTopologyService(gpuAlert, { service: "rack-12" })).toBe(
      true
    );
    expect(
      alertMatchesTopologyService(gpuAlert, { service: "gpu-node-a03" })
    ).toBe(true);
    expect(
      alertMatchesTopologyService(gpuAlert, { service: "gpu-node-a03-gpu0" })
    ).toBe(true);
  });

  it("does not match a different rack or GPU", () => {
    expect(alertMatchesTopologyService(gpuAlert, { service: "rack-11" })).toBe(
      false
    );
    expect(
      alertMatchesTopologyService(gpuAlert, { service: "gpu-node-a01-gpu0" })
    ).toBe(false);
  });
});

describe("incidentMatchesTopologyService", () => {
  const host = { service: "gpu-node-a03", display_name: "gpu-node-a03" };
  const gpu = {
    service: "gpu-node-a03-gpu0",
    display_name: "gpu-node-a03 GPU 0",
  };

  it("matches incident.services against the node name", () => {
    expect(
      incidentMatchesTopologyService(
        {
          id: "inc-1",
          services: ["gpu-node-a03"],
          enrichments: {},
        },
        host
      )
    ).toBe(true);
  });

  it("matches location enrichments", () => {
    expect(
      incidentMatchesTopologyService(
        {
          id: "inc-2",
          services: ["gpu-inference"],
          enrichments: { rack: "rack-12" },
        },
        { service: "rack-12", display_name: "rack-12" }
      )
    ).toBe(true);
  });

  it("matches via linked alerts so GPU incidents light up the host", () => {
    expect(
      incidentMatchesTopologyService(
        {
          id: "inc-3",
          services: ["gpu-inference"],
          enrichments: {},
        },
        host,
        [
          {
            service: "gpu-inference",
            incident: "inc-3",
            labels: { host: "gpu-node-a03", gpu_id: "gpu-node-a03-gpu0" },
          },
        ]
      )
    ).toBe(true);
    expect(
      incidentMatchesTopologyService(
        {
          id: "inc-3",
          services: ["gpu-inference"],
          enrichments: {},
        },
        gpu,
        [
          {
            service: "gpu-inference",
            incident: "inc-3",
            labels: { host: "gpu-node-a03", gpu_id: "gpu-node-a03-gpu0" },
          },
        ]
      )
    ).toBe(true);
  });

  it("does not match a different host", () => {
    expect(
      incidentMatchesTopologyService(
        {
          id: "inc-3",
          services: ["gpu-inference"],
          enrichments: {},
        },
        { service: "gpu-node-a01", display_name: "gpu-node-a01" },
        [
          {
            service: "gpu-inference",
            incident: "inc-3",
            labels: { host: "gpu-node-a03" },
          },
        ]
      )
    ).toBe(false);
  });
});
