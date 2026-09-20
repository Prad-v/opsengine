import { ApprovalsInbox } from "@/features/approvals";

export default function Page() {
  return (
    <div className="flex flex-col gap-4 p-4">
      <ApprovalsInbox />
    </div>
  );
}

export const metadata = {
  title: "Keep - Approvals",
  description: "Review and decide pending Keep approval requests",
};
