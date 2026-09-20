import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ApprovalPolicyForm } from "../ApprovalPolicyForm";
import { isApprovalPending } from "../../model/types";

describe("isApprovalPending", () => {
  it("detects a 202 pending payload", () => {
    expect(
      isApprovalPending({
        status: "pending",
        request_id: 7,
        approval: { id: 7 },
      })
    ).toBe(true);
    expect(isApprovalPending({ id: 1, name: "rule" })).toBe(false);
  });
});

describe("ApprovalPolicyForm", () => {
  it("submits a create_maintenance policy", async () => {
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    const onCancel = jest.fn();
    render(<ApprovalPolicyForm onSubmit={onSubmit} onCancel={onCancel} />);

    const nameInput = screen.getByPlaceholderText(
      "e.g. Long maintenance windows"
    );
    fireEvent.change(nameInput, { target: { value: "long-windows" } });

    fireEvent.click(screen.getByRole("button", { name: /create policy/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalled();
    });
    expect(onSubmit.mock.calls[0][0].action_type).toBe("create_maintenance");
    expect(onSubmit.mock.calls[0][0].name).toBe("long-windows");
  });
});
