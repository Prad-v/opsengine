import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useAISettings } from "@/features/settings/ai";
import { showErrorToast, showSuccessToast } from "@/shared/ui";
import { useAlertCatalog } from "../../model/useAlertCatalog";
import { AlertCatalogForm } from "../AlertCatalogForm";

jest.mock("@/entities/workflows/model", () => ({
  useWorkflows: () => ({ data: [] }),
}));

jest.mock("@/features/settings/ai", () => ({
  useAISettings: jest.fn(),
}));

jest.mock("@/shared/ui", () => ({
  showErrorToast: jest.fn(),
  showSuccessToast: jest.fn(),
}));

jest.mock("../../model/useAlertCatalog", () => ({
  useAlertCatalog: jest.fn(),
}));

describe("AlertCatalogForm AI enhance", () => {
  const mockEnhanceDescription = jest.fn();
  const mockOnSubmit = jest.fn();
  const mockOnCancel = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    (useAlertCatalog as jest.Mock).mockReturnValue({
      enhanceDescription: mockEnhanceDescription,
    });
    (useAISettings as jest.Mock).mockReturnValue({
      isAIEnabled: true,
      isLoading: false,
    });
  });

  it("enhances the draft description with Settings → AI", async () => {
    mockEnhanceDescription.mockResolvedValue({
      description:
        "NVIDIA_GPU_THERMAL fires when GPU temperature exceeds the DCGM threshold. Reset the GPU and page on-call.",
      model: "gpt-4o-mini",
    });

    render(
      <AlertCatalogForm
        initial={{
          id: 1,
          code: "NVIDIA_GPU_THERMAL",
          name: "NVIDIA GPU thermal going high",
          description: "gpu going high",
          auto_run_on: "alert",
        }}
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /AI/i }));

    await waitFor(() => {
      expect(mockEnhanceDescription).toHaveBeenCalledWith({
        code: "NVIDIA_GPU_THERMAL",
        name: "NVIDIA GPU thermal going high",
        description: "gpu going high",
        runbook_url: undefined,
        keep_workflow_id: undefined,
      });
    });

    expect(
      screen.getByDisplayValue(/NVIDIA_GPU_THERMAL fires when GPU temperature/)
    ).toBeInTheDocument();
    expect(showSuccessToast).toHaveBeenCalledWith("Description enhanced");
  });

  it("disables the AI button when Settings → AI is not configured", () => {
    (useAISettings as jest.Mock).mockReturnValue({
      isAIEnabled: false,
      isLoading: false,
    });

    render(
      <AlertCatalogForm
        initial={{
          id: 1,
          code: "NVIDIA_GPU_THERMAL",
          name: "NVIDIA GPU thermal",
          description: "gpu going high",
          auto_run_on: "alert",
        }}
        onSubmit={mockOnSubmit}
        onCancel={mockOnCancel}
      />
    );

    expect(screen.getByRole("button", { name: /AI/i })).toBeDisabled();
    expect(showErrorToast).not.toHaveBeenCalled();
  });
});
