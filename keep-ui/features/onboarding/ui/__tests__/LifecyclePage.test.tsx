import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { LifecyclePage } from "../LifecyclePage";
import { useOnboardingProgress } from "../../model/useOnboardingProgress";
import { useAlertCatalog } from "@/features/catalog/alert-code";
import { useApi } from "@/shared/lib/hooks/useApi";
import { DEFAULT_ONBOARDING_DRAFT } from "../../model/types";
import { computeOnboardingStatus } from "../../model/onboardingStatus";

jest.mock("../../model/useOnboardingProgress", () => ({
  useOnboardingProgress: jest.fn(),
}));

jest.mock("@/features/catalog/alert-code", () => ({
  useAlertCatalog: jest.fn(),
}));

jest.mock("@/shared/lib/hooks/useApi", () => ({
  useApi: jest.fn(),
}));

jest.mock("../OnboardingWizard", () => ({
  OnboardingWizard: ({ onClose }: { onClose?: () => void }) => (
    <div data-testid="onboarding-wizard">
      <button type="button" onClick={onClose}>
        Close
      </button>
    </div>
  ),
}));

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

jest.mock("@/shared/ui", () => ({
  KeepLoader: () => <div>loading</div>,
  DateTimeField: () => <span>just now</span>,
  PageTitle: ({ children }: { children: React.ReactNode }) => <h1>{children}</h1>,
  PageSubtitle: ({ children }: { children: React.ReactNode }) => (
    <p>{children}</p>
  ),
  showErrorToast: jest.fn(),
  showSuccessToast: jest.fn(),
}));

const catalogEntry = {
  id: 1,
  code: "NVIDIA_GPU_THERMAL",
  name: "NVIDIA GPU thermal",
  description: "GPU temperature exceeded threshold",
  keep_workflow_id: "wf-thermal",
  auto_run_on: "both" as const,
  disabled: false,
  updated_at: "2026-09-13T12:00:00Z",
};

function mockProgress(overrides: Record<string, unknown> = {}) {
  (useOnboardingProgress as jest.Mock).mockReturnValue({
    draft: DEFAULT_ONBOARDING_DRAFT,
    isLoading: false,
    installedProviders: [{ type: "grafana", tags: ["alert"] }],
    catalog: [catalogEntry],
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
    startNewLifecycle: jest.fn(),
    editLifecycle: jest.fn(),
    mutateCatalog: jest.fn(),
    mutateRules: jest.fn(),
    status: computeOnboardingStatus({
      installedProviders: [{ type: "grafana", tags: ["alert"] }],
      catalog: [catalogEntry],
      rules: [],
      workflows: [],
      selectedCode: "",
      workflowId: "",
      ruleId: "",
    }),
    ...overrides,
  });
}

describe("LifecyclePage", () => {
  const updateEntry = jest.fn();
  const deleteEntry = jest.fn();
  const apiDelete = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    updateEntry.mockResolvedValue({});
    deleteEntry.mockResolvedValue(undefined);
    apiDelete.mockResolvedValue({});
    (useAlertCatalog as jest.Mock).mockReturnValue({
      updateEntry,
      deleteEntry,
    });
    (useApi as jest.Mock).mockReturnValue({
      delete: apiDelete,
    });
    mockProgress();
  });

  it("shows an empty table state when there are no lifecycles", () => {
    mockProgress({ catalog: [], rules: [], workflows: [] });
    render(<LifecyclePage />);

    expect(screen.getByTestId("lifecycle-page")).toBeInTheDocument();
    expect(screen.getByText("No alert lifecycles yet")).toBeInTheDocument();
    expect(
      screen.getAllByRole("button", { name: "Onboard lifecycle" }).length
    ).toBeGreaterThan(0);
  });

  it("lists lifecycle entries with view, edit, pause, and delete", () => {
    render(<LifecyclePage />);

    expect(screen.getByTestId("lifecycle-table")).toBeInTheDocument();
    expect(screen.getByText("NVIDIA_GPU_THERMAL")).toBeInTheDocument();
    expect(screen.getByText("NVIDIA GPU thermal")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByLabelText("View NVIDIA_GPU_THERMAL")).toBeInTheDocument();
    expect(screen.getByLabelText("Edit NVIDIA_GPU_THERMAL")).toBeInTheDocument();
    expect(screen.getByLabelText("Pause NVIDIA_GPU_THERMAL")).toBeInTheDocument();
    expect(
      screen.getByLabelText("Delete NVIDIA_GPU_THERMAL")
    ).toBeInTheDocument();
  });

  it("opens the wizard from Onboard lifecycle", () => {
    const startNewLifecycle = jest.fn();
    mockProgress({ startNewLifecycle, catalog: [] });
    render(<LifecyclePage />);

    fireEvent.click(
      screen.getAllByRole("button", { name: "Onboard lifecycle" })[0]
    );
    expect(startNewLifecycle).toHaveBeenCalled();
    expect(screen.getByTestId("onboarding-wizard")).toBeInTheDocument();
  });

  it("opens the wizard when Edit is clicked", () => {
    const editLifecycle = jest.fn();
    mockProgress({ editLifecycle });
    render(<LifecyclePage />);

    fireEvent.click(screen.getByLabelText("Edit NVIDIA_GPU_THERMAL"));
    expect(editLifecycle).toHaveBeenCalledWith("NVIDIA_GPU_THERMAL");
    expect(screen.getByTestId("onboarding-wizard")).toBeInTheDocument();
  });

  it("opens the view drawer from View", () => {
    render(<LifecyclePage />);
    fireEvent.click(screen.getByLabelText("View NVIDIA_GPU_THERMAL"));
    expect(screen.getByTestId("lifecycle-view")).toHaveTextContent(
      "NVIDIA GPU thermal"
    );
    expect(screen.getByTestId("lifecycle-view")).toHaveTextContent(
      "GPU temperature exceeded threshold"
    );
    expect(screen.getByTestId("lifecycle-flow-map")).toBeInTheDocument();
    expect(screen.getByTestId("lifecycle-view")).toHaveTextContent(
      "Correlation → Incident → Workflow"
    );
  });

  it("pauses a lifecycle by disabling the catalog entry", async () => {
    render(<LifecyclePage />);
    fireEvent.click(screen.getByLabelText("Pause NVIDIA_GPU_THERMAL"));

    await waitFor(() => {
      expect(updateEntry).toHaveBeenCalledWith(
        1,
        expect.objectContaining({
          code: "NVIDIA_GPU_THERMAL",
          disabled: true,
        })
      );
    });
  });

  it("deletes the catalog entry and matching correlation rule", async () => {
    window.confirm = jest.fn(() => true);
    render(<LifecyclePage />);
    fireEvent.click(screen.getByLabelText("Delete NVIDIA_GPU_THERMAL"));

    await waitFor(() => {
      expect(deleteEntry).toHaveBeenCalledWith(1);
      expect(apiDelete).toHaveBeenCalledWith("/rules/rule-thermal");
    });
  });
});
