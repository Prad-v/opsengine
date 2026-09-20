import { ApprovalPoliciesPage } from "@/features/approvals";

export default function Page() {
  return (
    <div className="flex flex-col gap-4 p-4">
      <ApprovalPoliciesPage />
    </div>
  );
}

export const metadata = {
  title: "Keep - Approval policies",
  description: "Define when Keep actions require a second-person approval",
};
