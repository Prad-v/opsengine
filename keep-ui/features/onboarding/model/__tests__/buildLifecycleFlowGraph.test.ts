import { buildLifecycleFlowGraph } from "../buildLifecycleFlowGraph";
import { buildLifecycleRows } from "../lifecycleRows";
import type { AlertCatalogEntry } from "@/features/catalog/alert-code";

const catalogEntry = (
  overrides: Partial<AlertCatalogEntry> = {}
): AlertCatalogEntry => ({
  id: 1,
  code: "NVIDIA_GPU_THERMAL",
  name: "NVIDIA GPU thermal",
  auto_run_on: "both",
  keep_workflow_id: "wf-thermal",
  ...overrides,
});

function wiredRow() {
  return buildLifecycleRows({
    catalog: [catalogEntry()],
    rules: [
      {
        id: "rule-thermal",
        name: "NVIDIA_GPU_THERMAL incidents",
        definition_cel: 'labels.code == "NVIDIA_GPU_THERMAL"',
      },
    ],
    workflows: [
      {
        id: "wf-thermal",
        name: "Notify on NVIDIA_GPU_THERMAL",
        workflow_raw: "provider:\n  type: slack\n",
      },
    ],
    installedProviders: [{ type: "grafana", tags: ["alert"] }],
  })[0];
}

function unwiredRow() {
  return buildLifecycleRows({
    catalog: [
      catalogEntry({
        keep_workflow_id: null,
        auto_run_on: "none",
      }),
    ],
    rules: [],
    workflows: [],
    installedProviders: [],
  })[0];
}

describe("buildLifecycleFlowGraph", () => {
  it("builds correlation → incident → workflow nodes when wired", () => {
    const { nodes, edges } = buildLifecycleFlowGraph(wiredRow());

    expect(nodes.map((node) => node.id)).toEqual([
      "correlation",
      "incident",
      "workflow",
    ]);
    expect(nodes[0].data).toMatchObject({
      stage: "correlation",
      subtitle: "NVIDIA_GPU_THERMAL incidents",
      href: "/rules?id=rule-thermal",
      wired: true,
    });
    expect(nodes[1].data).toMatchObject({
      stage: "incident",
      subtitle: "NVIDIA_GPU_THERMAL",
      wired: true,
    });
    expect(nodes[2].data).toMatchObject({
      stage: "workflow",
      subtitle: "Notify on NVIDIA_GPU_THERMAL",
      href: "/workflows/wf-thermal",
      wired: true,
      badge: "auto-run both",
    });
    expect(edges.map((edge) => edge.id)).toEqual([
      "correlation-incident",
      "incident-workflow",
    ]);
    expect(edges[0].animated).toBe(true);
    expect(edges[1].animated).toBe(true);
  });

  it("marks missing correlation and workflow as unwired with dashed edges", () => {
    const { nodes, edges } = buildLifecycleFlowGraph(unwiredRow());

    expect(nodes[0].data.wired).toBe(false);
    expect(nodes[0].data.subtitle).toBe("No rule yet");
    expect(nodes[1].data.wired).toBe(false);
    expect(nodes[2].data.wired).toBe(false);
    expect(nodes[2].data.subtitle).toBe("Not attached");
    expect(edges[0].animated).toBe(false);
    expect(edges[1].animated).toBe(false);
    expect(edges[0].style?.strokeDasharray).toBe("6 4");
    expect(edges[1].style?.strokeDasharray).toBe("6 4");
  });

  it("shows paused badge on the incident node", () => {
    const row = buildLifecycleRows({
      catalog: [catalogEntry({ disabled: true })],
      rules: [
        {
          id: "rule-thermal",
          name: "NVIDIA_GPU_THERMAL incidents",
          definition_cel: 'labels.code == "NVIDIA_GPU_THERMAL"',
        },
      ],
      workflows: [{ id: "wf-thermal", name: "Notify" }],
      installedProviders: [{ type: "grafana", tags: ["alert"] }],
    })[0];

    const { nodes } = buildLifecycleFlowGraph(row);
    expect(nodes[1].data.badge).toBe("paused");
  });
});
