import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Status, Severity } from "@/entities/incidents/model/models";
import { TopologyNodeDrawer } from "../TopologyNodeDrawer";
import { TopologyService } from "@/app/(keep)/topology/model";
import { IncidentDto } from "@/entities/incidents/model";

const mockCreateRule = jest.fn();
const mockEndNow = jest.fn();
let mockRules: unknown[] = [];

jest.mock("@/utils/hooks/useMaintenanceRules", () => ({
  useMaintenanceRules: () => ({
    data: mockRules,
    createRule: mockCreateRule,
    endNow: mockEndNow,
  }),
}));

jest.mock("@/features/approvals", () => ({
  isApprovalPending: (body: { status?: string }) => body?.status === "pending",
  useApprovals: () => ({ requests: [] }),
}));

jest.mock("@/shared/ui", () => ({
  showErrorToast: jest.fn(),
  showSuccessToast: jest.fn(),
}));

const host: TopologyService = {
  id: "host-a03",
  service: "gpu-node-a03",
  display_name: "gpu-node-a03",
  category: "host",
  description: "NVIDIA H100 node",
  dependencies: [],
  application_ids: [],
  applications: [],
  is_manual: true,
};

function incident(overrides: Partial<IncidentDto> = {}): IncidentDto {
  return {
    id: "inc-1",
    user_generated_name: "GPU thermal on gpu-node-a03",
    ai_generated_name: "GPU thermal",
    user_summary: "",
    generated_summary: "",
    assignee: "",
    severity: Severity.High,
    status: Status.Firing,
    alerts_count: 2,
    alert_sources: ["grafana"],
    services: ["gpu-inference"],
    creation_time: new Date("2026-09-14T10:00:00Z"),
    is_candidate: false,
    rule_fingerprint: "",
    same_incident_in_the_past_id: "",
    following_incidents_ids: [],
    merged_into_incident_id: "",
    merged_by: "",
    merged_at: new Date(),
    fingerprint: "fp-1",
    enrichments: { host: "gpu-node-a03" },
    resolve_on: "all_resolved",
    ...overrides,
  };
}

describe("TopologyNodeDrawer", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockRules = [];
    mockCreateRule.mockResolvedValue({ id: 1 });
    mockEndNow.mockResolvedValue({ id: 1 });
  });

  it("lists active and historical incidents for the node", () => {
    render(
      <TopologyNodeDrawer
        isOpen
        onClose={jest.fn()}
        service={host}
        incidents={[
          incident(),
          incident({
            id: "inc-2",
            user_generated_name: "Previous ECC on gpu-node-a03",
            status: Status.Resolved,
          }),
        ]}
        alerts={[]}
      />
    );

    expect(screen.getByText("Active incidents (1)")).toBeInTheDocument();
    expect(screen.getByText("GPU thermal on gpu-node-a03")).toBeInTheDocument();
    expect(screen.getByText("Historical incidents (1)")).toBeInTheDocument();
    expect(
      screen.getByText("Previous ECC on gpu-node-a03")
    ).toBeInTheDocument();
  });

  it("creates a maintenance window for the node with reason and CEL", async () => {
    render(
      <TopologyNodeDrawer
        isOpen
        onClose={jest.fn()}
        service={host}
        incidents={[]}
        alerts={[]}
      />
    );

    fireEvent.click(
      screen.getByRole("button", { name: /put node in maintenance/i })
    );

    await waitFor(() => {
      expect(mockCreateRule).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Topology: gpu-node-a03 (Node down)",
          description: "Node down",
          cel_query:
            'labels.host == "gpu-node-a03" || service == "gpu-node-a03"',
          suppress: true,
          enabled: true,
          duration_seconds: 4 * 3600,
          ignore_statuses: ["resolved", "acknowledged"],
        })
      );
    });
  });

  it("ends an active maintenance window", async () => {
    mockRules = [
      {
        id: 42,
        name: "Topology: gpu-node-a03 (RMA)",
        description: "RMA",
        cel_query: 'labels.host == "gpu-node-a03" || service == "gpu-node-a03"',
        enabled: true,
        status: "active",
        start_time: new Date(Date.now() - 60_000),
        end_time: new Date(Date.now() + 3_600_000),
      },
    ];

    render(
      <TopologyNodeDrawer
        isOpen
        onClose={jest.fn()}
        service={host}
        incidents={[]}
        alerts={[]}
      />
    );

    expect(screen.getByText("In maintenance")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /end now/i }));

    await waitFor(() => {
      expect(mockEndNow).toHaveBeenCalledWith(42);
    });
  });
});
