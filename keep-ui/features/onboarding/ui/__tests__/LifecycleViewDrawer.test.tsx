import { render, screen } from "@testing-library/react";
import { LifecycleViewDrawer } from "../LifecycleViewDrawer";
import { buildLifecycleRows } from "../../model/lifecycleRows";

jest.mock("../LifecycleFlowMap", () => ({
  LifecycleFlowMap: () => <div data-testid="lifecycle-flow-map" />,
}));

jest.mock("@/shared/ui/Drawer", () => ({
  Drawer: ({
    isOpen,
    children,
  }: {
    isOpen: boolean;
    children: React.ReactNode;
  }) => (isOpen ? <div data-testid="drawer">{children}</div> : null),
}));

const row = buildLifecycleRows({
  catalog: [
    {
      id: 1,
      code: "NVIDIA_GPU_THERMAL",
      name: "NVIDIA GPU thermal",
      description: "GPU temperature exceeded threshold",
      auto_run_on: "both",
      keep_workflow_id: "wf-thermal",
    },
  ],
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

describe("LifecycleViewDrawer", () => {
  it("renders the correlation → incident → workflow map", () => {
    render(
      <LifecycleViewDrawer
        row={row}
        isOpen
        onClose={jest.fn()}
        onEdit={jest.fn()}
      />
    );

    expect(screen.getByTestId("lifecycle-view")).toHaveTextContent(
      "Correlation → Incident → Workflow"
    );
    expect(screen.getByTestId("lifecycle-flow-map")).toBeInTheDocument();
    expect(screen.getByTestId("lifecycle-view")).toHaveTextContent(
      "NVIDIA GPU thermal"
    );
  });

  it("hides content when closed", () => {
    render(
      <LifecycleViewDrawer
        row={row}
        isOpen={false}
        onClose={jest.fn()}
        onEdit={jest.fn()}
      />
    );

    expect(screen.queryByTestId("lifecycle-view")).not.toBeInTheDocument();
  });
});
