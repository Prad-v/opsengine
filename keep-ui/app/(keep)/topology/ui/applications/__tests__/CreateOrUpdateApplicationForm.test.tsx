import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { CreateOrUpdateApplicationForm } from "../create-or-update-application-form";
import { TopologyApplication } from "@/app/(keep)/topology/model";

jest.mock("../../TopologySearchAutocomplete", () => ({
  TopologySearchAutocomplete: () => <div>Search services</div>,
}));

const application: TopologyApplication = {
  id: "app-1",
  name: "NVIDIA GPU Inference",
  description: "Existing application",
  repository: "",
  services: [
    { id: "4", name: "gpu-node-a03", service: "gpu-node-a03" },
  ],
};

describe("CreateOrUpdateApplicationForm", () => {
  it("updates the existing application instead of creating a new one", async () => {
    const onSubmit = jest.fn().mockResolvedValue(undefined);

    render(
      <CreateOrUpdateApplicationForm
        action="edit"
        application={application}
        onSubmit={onSubmit}
        onCancel={jest.fn()}
        onDelete={jest.fn()}
      />
    );

    fireEvent.change(screen.getByPlaceholderText("Application name"), {
      target: { value: "NVIDIA GPU Inference (updated)" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Update" }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          id: "app-1",
          name: "NVIDIA GPU Inference (updated)",
        })
      );
    });
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("creates a new application only in create mode", async () => {
    const onSubmit = jest.fn().mockResolvedValue(undefined);

    render(
      <CreateOrUpdateApplicationForm
        action="create"
        application={{ services: application.services }}
        onSubmit={onSubmit}
        onCancel={jest.fn()}
      />
    );

    fireEvent.change(screen.getByPlaceholderText("Application name"), {
      target: { value: "Payments" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Payments",
        })
      );
    });
    expect(onSubmit.mock.calls[0][0]).not.toHaveProperty("id");
  });
});
