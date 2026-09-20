import { fireEvent, render, screen } from "@testing-library/react";
import CreateOrUpdateMaintenanceRule from "../create-or-update-maintenance-rule";

const mockCreateRule = jest.fn();
const mockUpdateRule = jest.fn();
const mockPreview = jest.fn();

jest.mock("next/navigation", () => ({
  useRouter: () => ({ replace: jest.fn() }),
}));

jest.mock("react-toastify", () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

jest.mock("@/shared/ui", () => ({
  showErrorToast: jest.fn(),
}));

jest.mock("@/entities/alerts/model", () => ({
  Status: {
    Firing: "firing",
    Resolved: "resolved",
    Acknowledged: "acknowledged",
    Suppressed: "suppressed",
    Pending: "pending",
  },
}));

jest.mock("@/utils/hooks/useMaintenanceRules", () => ({
  useMaintenanceRules: () => ({
    mutate: jest.fn(),
    createRule: mockCreateRule,
    updateRule: mockUpdateRule,
    preview: mockPreview,
  }),
}));

jest.mock("@/features/presets/presets-manager", () => ({
  AlertsRulesBuilder: ({
    updateOutputCEL,
    defaultQuery,
  }: {
    updateOutputCEL: (value: string) => void;
    defaultQuery: string;
  }) => (
    <input
      aria-label="CEL filter"
      value={defaultQuery}
      onChange={(event) => updateOutputCEL(event.target.value)}
    />
  ),
}));

jest.mock("react-datepicker", () => ({
  __esModule: true,
  default: ({
    selected,
    onChange,
  }: {
    selected: Date | null;
    onChange: (date: Date) => void;
  }) => (
    <input
      aria-label="Start at"
      value={selected?.toISOString?.() ?? ""}
      onChange={(event) => onChange(new Date(event.target.value))}
    />
  ),
}));

describe("CreateOrUpdateMaintenanceRule", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockPreview.mockResolvedValue({ count: 0, sample: [] });
  });

  it("defaults to show in feed as suppressed", () => {
    render(
      <CreateOrUpdateMaintenanceRule
        maintenanceToEdit={null}
        editCallback={jest.fn()}
      />
    );
    expect(
      screen.getByRole("radio", { name: /Show in feed as suppressed/i })
    ).toBeChecked();
    expect(
      screen.getByRole("radio", { name: /Hide from feed/i })
    ).not.toBeChecked();
  });

  it("disables create without a CEL filter and explains why", () => {
    render(
      <CreateOrUpdateMaintenanceRule
        maintenanceToEdit={null}
        editCallback={jest.fn()}
      />
    );
    expect(screen.getByRole("button", { name: "Create" })).toBeDisabled();
    expect(
      screen.getByText(/CEL filter is required/i)
    ).toBeInTheDocument();
  });

  it("enables create after name and CEL are filled", () => {
    render(
      <CreateOrUpdateMaintenanceRule
        maintenanceToEdit={null}
        editCallback={jest.fn()}
      />
    );
    fireEvent.change(screen.getByPlaceholderText("Maintenance Name"), {
      target: { value: "GPU firmware" },
    });
    fireEvent.change(screen.getByLabelText("CEL filter"), {
      target: { value: 'source == "prometheus"' },
    });
    expect(screen.getByRole("button", { name: "Create" })).toBeEnabled();
  });
});
