import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { WorkflowStep } from "../WorkflowStep";
import type { AlertCatalogEntry } from "@/features/catalog/alert-code";
import type { Workflow } from "@/shared/api/workflows";

const mockCreateWorkflow = jest.fn();
const mockOnAttach = jest.fn();
const mockOnWorkflowCreated = jest.fn();

jest.mock("@/entities/workflows/model", () => ({
  useWorkflowActions: () => ({
    createWorkflow: mockCreateWorkflow,
  }),
}));

jest.mock("@/shared/ui", () => ({
  showErrorToast: jest.fn(),
  showSuccessToast: jest.fn(),
}));

const catalog: AlertCatalogEntry[] = [
  {
    id: 1,
    code: "NVIDIA_GPU_THERMAL",
    name: "NVIDIA GPU thermal",
    auto_run_on: "both",
    keep_workflow_id: "wf-gpu",
  },
];

const workflows: Workflow[] = [
  {
    id: "wf-gpu",
    name: "Notify on NVIDIA_GPU_THERMAL",
    description: "Created by the lifecycle wizard",
    created_by: "test",
    creation_time: "",
    interval: "",
    providers: [],
    triggers: [],
    disabled: false,
    last_execution_time: "",
    last_execution_status: "",
    last_updated: "",
    workflow_raw: "",
    workflow_raw_id: "onboarding-notify-nvidia_gpu_thermal",
  },
  {
    id: "wf-cpu",
    name: "Notify on HIGH_CPU",
    description: "",
    created_by: "test",
    creation_time: "",
    interval: "",
    providers: [],
    triggers: [],
    disabled: false,
    last_execution_time: "",
    last_execution_status: "",
    last_updated: "",
    workflow_raw: "",
    workflow_raw_id: "onboarding-notify-high-cpu",
  },
];

describe("WorkflowStep", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockOnAttach.mockResolvedValue(undefined);
    mockCreateWorkflow.mockResolvedValue({ workflow_id: "wf-new" });
  });

  it("shows workflow name as a dropdown and attaches the selected workflow", async () => {
    render(
      <WorkflowStep
        selectedCode="NVIDIA_GPU_THERMAL"
        catalog={catalog}
        workflows={workflows}
        workflowId="wf-gpu"
        onSelectCode={jest.fn()}
        onWorkflowCreated={mockOnWorkflowCreated}
        onAttach={mockOnAttach}
      />
    );

    expect(screen.getByTestId("workflow-attach-step")).toBeInTheDocument();
    expect(screen.getByText("Workflow name")).toBeInTheDocument();
    expect(
      screen.getAllByText("Notify on NVIDIA_GPU_THERMAL").length
    ).toBeGreaterThan(0);
    expect(
      screen.getByRole("link", { name: "Notify on NVIDIA_GPU_THERMAL" })
    ).toHaveAttribute("href", "/workflows/wf-gpu");

    fireEvent.click(screen.getByRole("button", { name: "Attach workflow" }));

    await waitFor(() => {
      expect(mockOnAttach).toHaveBeenCalledWith(catalog[0], "wf-gpu", "both");
    });
    expect(mockOnWorkflowCreated).toHaveBeenCalledWith("wf-gpu");
    expect(mockCreateWorkflow).not.toHaveBeenCalled();
  });

  it("creates a notify workflow when the create option is selected", async () => {
    render(
      <WorkflowStep
        selectedCode="NVIDIA_GPU_THERMAL"
        catalog={[{ ...catalog[0], keep_workflow_id: undefined }]}
        workflows={workflows}
        workflowId=""
        onSelectCode={jest.fn()}
        onWorkflowCreated={mockOnWorkflowCreated}
        onAttach={mockOnAttach}
      />
    );

    expect(screen.getByRole("button", { name: "Create and attach" })).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Create and attach" })
    );

    await waitFor(() => {
      expect(mockCreateWorkflow).toHaveBeenCalled();
      expect(mockOnAttach).toHaveBeenCalledWith(
        expect.objectContaining({ code: "NVIDIA_GPU_THERMAL" }),
        "wf-new",
        "both"
      );
    });
  });
});
