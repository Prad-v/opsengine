"use client";

import { Badge, Subtitle } from "@tremor/react";
import { LinkWithIcon } from "components/LinkWithIcon";
import { Session } from "next-auth";
import { HiOutlineClipboardCheck } from "react-icons/hi";
import { useApprovals } from "@/features/approvals";
import { useConfig } from "@/utils/hooks/useConfig";
import { useTenantConfiguration } from "@/utils/hooks/useTenantConfiguration";

type ApprovalsLinkProps = { session: Session | null };

export function ApprovalsLink({ session }: ApprovalsLinkProps) {
  const { data: tenantConfig } = useTenantConfiguration();
  const { data: envConfig } = useConfig();
  const hidden =
    !!tenantConfig?.HIDE_NAVBAR_APPROVALS ||
    !!(envConfig as { HIDE_NAVBAR_APPROVALS?: boolean } | undefined)
      ?.HIDE_NAVBAR_APPROVALS;
  const { requests } = useApprovals({ status: "pending" });

  if (!session || hidden) {
    return null;
  }

  return (
    <li className="list-none">
      <LinkWithIcon
        href="/approvals"
        icon={HiOutlineClipboardCheck}
        testId="approvals-inbox"
      >
        <Subtitle className="text-xs">Approvals</Subtitle>
        {requests.length > 0 ? (
          <Badge color="orange" size="xs" className="ml-1">
            {requests.length}
          </Badge>
        ) : null}
      </LinkWithIcon>
    </li>
  );
}
