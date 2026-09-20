import { renderHook, waitFor } from "@testing-library/react";
import { useApi } from "@/shared/lib/hooks/useApi";
import { useMaintenanceRules } from "../useMaintenanceRules";

jest.mock("@/shared/lib/hooks/useApi");
jest.mock("react-toastify", () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));
jest.mock("@/shared/ui", () => ({
  showErrorToast: jest.fn(),
}));

describe("useMaintenanceRules", () => {
  const mockGet = jest.fn();
  const mockPost = jest.fn();
  const mockPut = jest.fn();
  const mockDelete = jest.fn();

  beforeEach(() => {
    (useApi as jest.Mock).mockReturnValue({
      get: mockGet,
      post: mockPost,
      put: mockPut,
      delete: mockDelete,
      isReady: () => true,
    });
    mockGet.mockResolvedValue([]);
    mockPost.mockResolvedValue({ id: 1 });
    mockPut.mockResolvedValue({ id: 1 });
    mockDelete.mockResolvedValue({});
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it("deletes a rule and revalidates the list", async () => {
    const { result } = renderHook(() => useMaintenanceRules());
    await waitFor(() => expect(result.current.deleteRule).toBeDefined());
    await result.current.deleteRule(9);
    expect(mockDelete).toHaveBeenCalledWith("/maintenance/9");
  });

  it("ends a rule now and revalidates", async () => {
    const { result } = renderHook(() => useMaintenanceRules());
    await waitFor(() => expect(result.current.endNow).toBeDefined());
    await result.current.endNow(3);
    expect(mockPost).toHaveBeenCalledWith("/maintenance/3/end-now");
  });

  it("extends a rule by the requested duration", async () => {
    const { result } = renderHook(() => useMaintenanceRules());
    await waitFor(() => expect(result.current.extend).toBeDefined());
    await result.current.extend(3, 1800);
    expect(mockPost).toHaveBeenCalledWith("/maintenance/3/extend", {
      duration_seconds: 1800,
    });
  });
});
