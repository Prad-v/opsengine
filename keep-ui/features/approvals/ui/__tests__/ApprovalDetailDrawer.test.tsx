import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ApprovalDetailDrawer } from "../ApprovalDetailDrawer";
import type { ApprovalRequest } from "../../model/types";

const request: ApprovalRequest = {
  id: 3,
  action_type: "create_maintenance",
  status: "pending",
  title: "Long GPU window",
  summary: "4h firmware",
  requested_by: "alice@example.com",
  requested_at: "2026-09-14T00:00:00Z",
  payload: { duration_seconds: 14400 },
  context: {},
  callback: {},
  result: {},
};

describe("ApprovalDetailDrawer", () => {
  it("approves the pending request", async () => {
    const onApprove = jest.fn().mockResolvedValue(undefined);
    const onReject = jest.fn();
    const onCancel = jest.fn();
    const onClose = jest.fn();
    render(
      <ApprovalDetailDrawer
        request={request}
        onApprove={onApprove}
        onReject={onReject}
        onCancel={onCancel}
        onClose={onClose}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: /approve/i }));
    await waitFor(() => {
      expect(onApprove).toHaveBeenCalled();
    });
  });
});
