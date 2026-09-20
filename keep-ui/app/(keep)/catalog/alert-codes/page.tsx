import { AlertCatalogPage } from "@/features/catalog/alert-code";

export default function Page() {
  return (
    <div className="flex flex-col gap-4 p-4">
      <AlertCatalogPage />
    </div>
  );
}

export const metadata = {
  title: "Keep - Alert codes",
  description:
    "Register reserved alert codes and link Keep workflows as automated runbooks",
};
