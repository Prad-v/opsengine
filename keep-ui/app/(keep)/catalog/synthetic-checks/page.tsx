import { SyntheticCheckCatalogPage } from "@/features/catalog/synthetic-check";

export default function Page() {
  return (
    <div className="flex flex-col gap-4 p-4">
      <SyntheticCheckCatalogPage />
    </div>
  );
}

export const metadata = {
  title: "Keep - Synthetic checks",
  description:
    "Manage Temporal-backed HTTP, TCP, and DNS synthetic checks",
};
