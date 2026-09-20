"use client";

import { Subtitle } from "@tremor/react";
import { LinkWithIcon } from "components/LinkWithIcon";
import { Session } from "next-auth";
import { Disclosure } from "@headlessui/react";
import { IoChevronUp } from "react-icons/io5";
import {
  HiOutlineCollection,
  HiOutlineStatusOnline,
  HiOutlineTag,
} from "react-icons/hi";
import clsx from "clsx";
import { useConfig } from "@/utils/hooks/useConfig";
import { useTenantConfiguration } from "@/utils/hooks/useTenantConfiguration";
import { ReactNode } from "react";
import Skeleton from "react-loading-skeleton";
import "react-loading-skeleton/dist/skeleton.css";

type CatalogLinksProps = { session: Session | null };

type TogglableLinkProps = {
  disabledConfigKey: string;
  children: ReactNode;
};

const TogglableLink = ({ children, disabledConfigKey }: TogglableLinkProps) => {
  const { data: tenantConfig, isLoading } = useTenantConfiguration();
  const { data: envConfig } = useConfig();

  if (isLoading || !tenantConfig) {
    return (
      <div className="flex gap-2 items-center h-7 pl-3">
        <Skeleton className="min-h-5 min-w-5" />
        <Skeleton
          className="min-h-5 min-w-24"
          containerClassName="min-h-5 min-w-24"
        />
      </div>
    );
  }

  if (
    !tenantConfig?.[disabledConfigKey] &&
    !(envConfig as any)?.[disabledConfigKey]
  ) {
    return <>{children}</>;
  }
};

export const CatalogLinks = ({ session }: CatalogLinksProps) => {
  const isNOCRole = session?.userRole === "noc";
  const { data: tenantConfig } = useTenantConfiguration();
  const catalogKeys = {
    HIDE_NAVBAR_TEMPORAL_WORKFLOWS: "HIDE_NAVBAR_TEMPORAL_WORKFLOWS",
    HIDE_NAVBAR_SYNTHETIC_CHECKS: "HIDE_NAVBAR_SYNTHETIC_CHECKS",
    HIDE_NAVBAR_ALERT_CODES: "HIDE_NAVBAR_ALERT_CODES",
    HIDE_NAVBAR_APPROVAL_POLICIES: "HIDE_NAVBAR_APPROVAL_POLICIES",
  };

  if (isNOCRole) {
    return null;
  }

  if (!Object.values(catalogKeys).some((key) => !tenantConfig?.[key])) {
    return null;
  }

  return (
    <Disclosure as="div" className="space-y-0.5" defaultOpen>
      <Disclosure.Button className="w-full flex justify-between items-center px-2">
        {({ open }) => (
          <>
            {tenantConfig && (
              <>
                <Subtitle className="text-xs ml-2 text-gray-900 font-medium uppercase">
                  Catalog
                </Subtitle>
                <IoChevronUp
                  className={clsx(
                    { "rotate-180": open },
                    "mr-2 text-slate-400"
                  )}
                />
              </>
            )}
            {!tenantConfig && (
              <div className="flex items-center h-7 pl-2">
                <Skeleton className="min-h-5 min-w-36" />
              </div>
            )}
          </>
        )}
      </Disclosure.Button>

      <Disclosure.Panel as="ul" className="space-y-0.5 p-1 pr-1">
        <TogglableLink disabledConfigKey={catalogKeys.HIDE_NAVBAR_ALERT_CODES}>
          <li>
            <LinkWithIcon
              href="/catalog/alert-codes"
              icon={HiOutlineTag}
              testId="alert-code-catalog"
            >
              <Subtitle className="text-xs">Alert codes</Subtitle>
            </LinkWithIcon>
          </li>
        </TogglableLink>
        <TogglableLink
          disabledConfigKey={catalogKeys.HIDE_NAVBAR_APPROVAL_POLICIES}
        >
          <li>
            <LinkWithIcon
              href="/catalog/approval-policies"
              icon={HiOutlineCollection}
              testId="approval-policies-catalog"
            >
              <Subtitle className="text-xs">Approval policies</Subtitle>
            </LinkWithIcon>
          </li>
        </TogglableLink>
        <TogglableLink
          disabledConfigKey={catalogKeys.HIDE_NAVBAR_TEMPORAL_WORKFLOWS}
        >
          <li>
            <LinkWithIcon
              href="/catalog/temporal-workflows"
              icon={HiOutlineCollection}
              testId="temporal-workflow-catalog"
            >
              <Subtitle className="text-xs">Temporal workflow</Subtitle>
            </LinkWithIcon>
          </li>
        </TogglableLink>
        <TogglableLink
          disabledConfigKey={catalogKeys.HIDE_NAVBAR_SYNTHETIC_CHECKS}
        >
          <li>
            <LinkWithIcon
              href="/catalog/synthetic-checks"
              icon={HiOutlineStatusOnline}
              testId="synthetic-checks-catalog"
            >
              <Subtitle className="text-xs">Synthetic checks</Subtitle>
            </LinkWithIcon>
          </li>
        </TogglableLink>
      </Disclosure.Panel>
    </Disclosure>
  );
};
