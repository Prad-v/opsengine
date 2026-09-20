import { Status, Severity } from "@/entities/incidents/model/models";
import { TopologyService } from "@/app/(keep)/topology/model";
import { getNodesAndEdgesFromTopologyData } from "../getNodesAndEdgesFromTopologyData";

const host: TopologyService = {
  id: "1",
  service: "gpu-node-a03",
  display_name: "gpu-node-a03",
  category: "host",
  dependencies: [],
  application_ids: [],
  applications: [],
  is_manual: true,
};

describe("getNodesAndEdgesFromTopologyData", () => {
  it("counts incidents via location matching and flags maintenance", () => {
    const { nodeMap } = getNodesAndEdgesFromTopologyData(
      [host],
      new Map(),
      [
        {
          id: "inc-1",
          user_generated_name: "thermal",
          ai_generated_name: "thermal",
          user_summary: "",
          generated_summary: "",
          assignee: "",
          severity: Severity.High,
          status: Status.Firing,
          alerts_count: 1,
          alert_sources: [],
          services: ["gpu-inference"],
          creation_time: new Date(),
          is_candidate: false,
          rule_fingerprint: "",
          same_incident_in_the_past_id: "",
          following_incidents_ids: [],
          merged_into_incident_id: "",
          merged_by: "",
          merged_at: new Date(),
          fingerprint: "fp",
          enrichments: { host: "gpu-node-a03" },
          resolve_on: "all_resolved",
        },
      ],
      [],
      jest.fn(),
      [
        {
          id: 7,
          name: "Topology: gpu-node-a03 (RMA)",
          created_by: "keep",
          cel_query:
            'labels.host == "gpu-node-a03" || service == "gpu-node-a03"',
          start_time: new Date(Date.now() - 60_000),
          end_time: new Date(Date.now() + 3_600_000),
          suppress: true,
          enabled: true,
          ignore_statuses: ["resolved", "acknowledged"],
          status: "active",
        },
      ]
    );

    const node = nodeMap.get("1");
    expect(node?.data.incidents).toBe(1);
    expect(node?.data.inMaintenance).toBe(true);
  });
});
