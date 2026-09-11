import { TemporalWorkflowCatalogPage } from "@/features/catalog/temporal-workflow";

export default function Page() {
  return (
    <div className="flex flex-col gap-4 p-4">
      <TemporalWorkflowCatalogPage />
    </div>
  );
}

export const metadata = {
  title: "Keep - Temporal workflow catalog",
  description:
    "Browse Keep-managed Temporal workflows registered on your Temporal providers",
};
