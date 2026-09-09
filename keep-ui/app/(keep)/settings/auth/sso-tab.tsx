import SSOSettings from "./sso-settings";

interface SSOSubTabProps {
  selected?: boolean;
}

export default function SSOSubTab({ selected = true }: SSOSubTabProps) {
  return <SSOSettings selected={selected} />;
}
