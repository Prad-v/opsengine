import { renderHook, waitFor } from "@testing-library/react";
import { useApi } from "@/shared/lib/hooks/useApi";
import { useAlertCatalog } from "../useAlertCatalog";

jest.mock("@/shared/lib/hooks/useApi");

describe("useAlertCatalog", () => {
  const mockGet = jest.fn();
  const mockPost = jest.fn();

  beforeEach(() => {
    (useApi as jest.Mock).mockReturnValue({
      get: mockGet,
      post: mockPost,
      put: jest.fn(),
      delete: jest.fn(),
      isReady: () => true,
    });
    mockGet.mockResolvedValue([]);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it("posts the draft to Settings → AI enhance endpoint", async () => {
    mockPost.mockResolvedValue({
      description: "Enhanced NVIDIA GPU thermal description",
      model: "gpt-4o-mini",
    });

    const { result } = renderHook(() => useAlertCatalog());

    await waitFor(() => {
      expect(result.current.enhanceDescription).toBeDefined();
    });

    const enhanced = await result.current.enhanceDescription({
      code: "NVIDIA_GPU_THERMAL",
      description: "gpu going high",
    });

    expect(mockPost).toHaveBeenCalledWith("/alert-catalog/enhance-description", {
      code: "NVIDIA_GPU_THERMAL",
      description: "gpu going high",
    });
    expect(enhanced.description).toContain("NVIDIA GPU thermal");
    expect(enhanced.model).toBe("gpt-4o-mini");
  });
});
