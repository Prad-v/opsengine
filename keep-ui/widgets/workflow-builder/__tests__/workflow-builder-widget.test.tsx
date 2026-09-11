import { render, screen } from "@testing-library/react";
import { WorkflowBuilderWidgetSafe } from "../workflow-builder-widget-safe";
import { useAISettings } from "@/features/settings/ai";
import { WorkflowBuilderWidget } from "../workflow-builder-widget";

// Mock the actual WorkflowBuilderWidget component
jest.mock("../workflow-builder-widget", () => ({
  WorkflowBuilderWidget: jest.fn((props) => (
    <div data-testid="workflow-builder">
      <span>workflowRaw: {props.workflowRaw}</span>
      <span>workflowId: {props.workflowId}</span>
    </div>
  )),
}));

// Mock CopilotKit
jest.mock("@copilotkit/react-core", () => ({
  CopilotKit: ({ children, runtimeUrl: _, ...props }: any) => (
    <div data-testid="copilot-wrapper" {...props}>
      {children}
    </div>
  ),
}));

jest.mock("@/features/settings/ai", () => ({
  useAISettings: jest.fn(),
}));

describe("WorkflowBuilderWidgetSafe", () => {
  const mockWorkflowRaw = JSON.stringify({ test: "workflow" });
  const mockWorkflowId = "test-workflow-id";

  beforeEach(() => {
    jest.clearAllMocks();
    (WorkflowBuilderWidget as jest.Mock).mockClear();
  });

  it("should render WorkflowBuilderWidget with props when AI is not enabled", () => {
    (useAISettings as jest.Mock).mockReturnValue({
      isAIEnabled: false,
      isLoading: false,
    });

    render(
      <WorkflowBuilderWidgetSafe
        workflowRaw={mockWorkflowRaw}
        workflowId={mockWorkflowId}
      />
    );

    expect(WorkflowBuilderWidget).toHaveBeenCalledWith(
      {
        workflowRaw: mockWorkflowRaw,
        workflowId: mockWorkflowId,
      },
      undefined
    );

    expect(screen.getByTestId("workflow-builder")).toBeInTheDocument();
    expect(
      screen.getByText(`workflowRaw: ${mockWorkflowRaw}`)
    ).toBeInTheDocument();
    expect(
      screen.getByText(`workflowId: ${mockWorkflowId}`)
    ).toBeInTheDocument();
    expect(screen.queryByTestId("copilot-wrapper")).not.toBeInTheDocument();
  });

  it("should wrap WorkflowBuilderWidget with CopilotKit when AI is enabled", () => {
    (useAISettings as jest.Mock).mockReturnValue({
      isAIEnabled: true,
      isLoading: false,
    });

    render(
      <WorkflowBuilderWidgetSafe
        workflowRaw={mockWorkflowRaw}
        workflowId={mockWorkflowId}
      />
    );

    expect(screen.getByTestId("copilot-wrapper")).toBeInTheDocument();

    expect(WorkflowBuilderWidget).toHaveBeenCalledWith(
      {
        workflowRaw: mockWorkflowRaw,
        workflowId: mockWorkflowId,
      },
      undefined
    );

    const copilotWrapper = screen.getByTestId("copilot-wrapper");
    expect(copilotWrapper).toContainElement(
      screen.getByTestId("workflow-builder")
    );
  });
});
