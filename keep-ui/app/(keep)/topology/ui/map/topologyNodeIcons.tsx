import {
  Boxes,
  Building2,
  Cpu,
  Globe,
  LayoutGrid,
  Monitor,
  Server,
  type LucideIcon,
} from "lucide-react";
import { clsx } from "clsx";

const CATEGORY_ICONS: Record<string, LucideIcon> = {
  region: Globe,
  datacenter: Building2,
  row: LayoutGrid,
  rack: Server,
  host: Monitor,
  gpu: Cpu,
  service: Boxes,
};

export type TopologyCategoryIconProps = {
  category?: string;
  className?: string;
};

export function TopologyCategoryIcon({
  category,
  className,
}: TopologyCategoryIconProps) {
  const key = (category || "service").toLowerCase();
  const Icon = CATEGORY_ICONS[key] ?? Boxes;
  return (
    <Icon
      className={clsx("shrink-0", className)}
      aria-hidden={false}
      aria-label={category || "service"}
    />
  );
}
