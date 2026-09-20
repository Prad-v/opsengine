import { fireEvent, render, screen } from "@testing-library/react";
import { OnboardingWizard } from "../OnboardingWizard";
import { useOnboardingProgress } from "../../model/useOnboardingProgress";
import { computeOnboardingStatus } from "../../model/onboardingStatus";
import { DEFAULT_ONBOARDING_DRAFT } from "../../model/types";

const mockPush = jest.fn();

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: jest.fn() }),
}));

jest.mock("../../model/useOnboardingProgress", () => ({
  useOnboardingProgress: jest.fn(),
}));

jest.mock("@/features/catalog/alert-code", () => ({
  useAlertCatalog: () => ({
    createEntry: jest.fn(),
    updateEntry: jest.fn(),
  }),
  AlertCatalogForm: () => <div>alert-catalog-form</div>,
}));

jest.mock("../steps/ProvidersStep", () => ({
  ProvidersStep: () => <div>providers-step</div>,
}));

jest.mock("../steps/AlertCodesStep", () => ({
  AlertCodesStep: () => <div>alert-codes-step</div>,
}));

jest.mock("../steps/CorrelationStep", () => ({
  CorrelationStep: () => <div>correlation-step</div>,
}));

jest.mock("../steps/WorkflowStep", () => ({
  WorkflowStep: () => <div>workflow-step</div>,
}));

jest.mock("../steps/NotificationStep", () => ({
  NotificationStep: () => <div>notification-step</div>,
}));

describe("OnboardingWizard", () => {
  const setDraft = jest.fn();
  const startNewLifecycle = jest.fn();
  const dismissLanding = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    const status = computeOnboardingStatus({
      installedProviders: [],
      catalog: [],
      rules: [],
      workflows: [],
      selectedCode: "",
      workflowId: "",
      ruleId: "",
    });
    (useOnboardingProgress as jest.Mock).mockReturnValue({
      draft: DEFAULT_ONBOARDING_DRAFT,
      setDraft,
      status,
      isLoading: false,
      isLocalhost: true,
      installedProviders: [],
      availableProviders: [],
      catalog: [],
      workflows: [],
      startNewLifecycle,
      dismissLanding,
      mutateProviders: jest.fn(),
      mutateCatalog: jest.fn(),
      mutateRules: jest.fn(),
      mutateWorkflows: jest.fn(),
    });
  });

  it("renders a repeatable lifecycle wizard and starts on providers", () => {
    render(<OnboardingWizard />);

    expect(screen.getByTestId("onboarding-wizard")).toBeInTheDocument();
    expect(
      screen.getByText("Onboard an alert lifecycle")
    ).toBeInTheDocument();
    expect(screen.getByText("Providers")).toBeInTheDocument();
    expect(screen.getByText("Alert codes")).toBeInTheDocument();
    expect(screen.getByText("Correlation")).toBeInTheDocument();
    expect(screen.getByText("Workflow")).toBeInTheDocument();
    expect(screen.getByText("Notification")).toBeInTheDocument();
    expect(screen.getByText("providers-step")).toBeInTheDocument();
    expect(screen.getAllByTestId("onboard-another").length).toBeGreaterThan(0);
  });

  it("advances to the next step when Continue is clicked", () => {
    render(<OnboardingWizard />);
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(setDraft).toHaveBeenCalled();
  });

  it("closes without consuming the wizard and goes to incidents", () => {
    render(<OnboardingWizard />);
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(dismissLanding).toHaveBeenCalled();
    expect(mockPush).toHaveBeenCalledWith("/incidents");
  });

  it("returns to the caller when onClose is provided", () => {
    const onClose = jest.fn();
    render(<OnboardingWizard onClose={onClose} />);
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(dismissLanding).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
    expect(mockPush).not.toHaveBeenCalled();
  });

  it("starts a new lifecycle run from Onboard another", () => {
    render(<OnboardingWizard />);
    fireEvent.click(screen.getAllByTestId("onboard-another")[0]);
    expect(startNewLifecycle).toHaveBeenCalled();
  });
});
