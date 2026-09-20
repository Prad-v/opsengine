import { fireEvent, render, screen } from "@testing-library/react";
import { ApprovalsInbox } from "../ApprovalsInbox";

jest.mock("../../model/useApprovals", () => ({
  useApprovals: () => ({
    requests: [
      {
        id: 7,
        title: "Put gpu-node-a03 in maintenance",
        action_type: "node_maintenance",
        status: "pending",
        requested_by: "alice@example.com",
        requested_at: "2026-09-14T00:00:00Z",
        payload: {},
        context: {},
        callback: {},
        result: {},
      },
    ],
    isLoading: false,
    error: undefined,
    mutate: jest.fn(),
    subscribe: jest.fn(),
    unsubscribe: jest.fn(),
  }),
}));

jest.mock("../../model/useApprovalActions", () => ({
  useApprovalActions: () => ({
    approve: jest.fn(),
    reject: jest.fn(),
    cancel: jest.fn(),
  }),
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

describe("ApprovalsInbox", () => {
  it("lists pending requests", () => {
    render(<ApprovalsInbox />);
    expect(screen.getByText("Put gpu-node-a03 in maintenance")).toBeInTheDocument();
    expect(screen.getByText("node_maintenance")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Put gpu-node-a03 in maintenance"));
    expect(screen.getByTestId("drawer")).toBeInTheDocument();
  });
});
