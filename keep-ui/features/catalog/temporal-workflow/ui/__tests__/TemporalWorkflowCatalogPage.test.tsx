import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { showErrorToast, showSuccessToast } from "@/shared/ui";
import { useTemporalWorkflowCatalog } from "../../model/useTemporalWorkflowCatalog";
import { TemporalWorkflowCatalogPage } from "../TemporalWorkflowCatalogPage";

jest.mock("../../model/useTemporalWorkflowCatalog", () => ({
  useTemporalWorkflowCatalog: jest.fn(),
}));

jest.mock("@/shared/ui", () => ({
  showErrorToast: jest.fn(),
  showSuccessToast: jest.fn(),
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

jest.mock("@/components/ui", () => ({
  DynamicImageProviderIcon: () => <span data-testid="provider-icon" />,
}));

jest.mock("../TemporalWorkflowForm", () => ({
  TemporalWorkflowForm: ({
    initial,
    onCancel,
  }: {
    initial?: { name: string } | null;
    onCancel: () => void;
  }) => (
    <div data-testid="temporal-form">
      {initial ? `Editing ${initial.name}` : "Creating"}
      <button type="button" onClick={onCancel}>
        Cancel
      </button>
    </div>
  ),
}));

const catalogEntry = {
  id: 1,
  catalog_key: "list-and-zip-directory",
  name: "List and Zip Directory",
  description: "Run ls and zip the listing",
  workflow_type: "ListAndZipDirectory",
  task_queue: "keep-ops",
  provider_id: "temporal-1",
  provider_name: "Local Temporal",
  input_mapping: { incident_id: "id" },
  disabled: false,
};

describe("TemporalWorkflowCatalogPage", () => {
  const mutate = jest.fn();
  const createEntry = jest.fn();
  const updateEntry = jest.fn();
  const deleteEntry = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    window.confirm = jest.fn(() => true);
    (useTemporalWorkflowCatalog as jest.Mock).mockReturnValue({
      catalog: [catalogEntry],
      error: undefined,
      isLoading: false,
      mutate,
      createEntry,
      updateEntry,
      deleteEntry,
    });
  });

  it("opens view drawer from the View button", () => {
    render(<TemporalWorkflowCatalogPage />);

    fireEvent.click(screen.getByRole("button", { name: "View" }));

    const view = screen.getByTestId("temporal-workflow-view");
    expect(view).toBeInTheDocument();
    expect(view).toHaveTextContent("List and Zip Directory");
    expect(view).toHaveTextContent("keep-ops");
    expect(view).toHaveTextContent("incident_id");
  });

  it("opens edit form from the Edit button", () => {
    render(<TemporalWorkflowCatalogPage />);

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));

    expect(screen.getByTestId("temporal-form")).toHaveTextContent(
      "Editing List and Zip Directory"
    );
  });

  it("deletes a catalog entry after confirmation", async () => {
    deleteEntry.mockResolvedValue({ message: "deleted" });
    render(<TemporalWorkflowCatalogPage />);

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() => {
      expect(deleteEntry).toHaveBeenCalledWith(1);
    });
    expect(showSuccessToast).toHaveBeenCalledWith("Temporal workflow deleted");
    expect(showErrorToast).not.toHaveBeenCalled();
  });

  it("opens view when a row is clicked", () => {
    render(<TemporalWorkflowCatalogPage />);

    fireEvent.click(
      screen.getByTestId("temporal-catalog-row-list-and-zip-directory")
    );

    expect(screen.getByTestId("temporal-workflow-view")).toBeInTheDocument();
  });
});
