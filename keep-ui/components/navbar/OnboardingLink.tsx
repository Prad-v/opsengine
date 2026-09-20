"use client";

import { Subtitle } from "@tremor/react";
import { LinkWithIcon } from "components/LinkWithIcon";
import { Session } from "next-auth";
import { HiOutlineSparkles } from "react-icons/hi2";
import { useOnboardingProgress } from "@/features/onboarding/model/useOnboardingProgress";

type OnboardingLinkProps = { session: Session | null };

export const OnboardingLink = ({ session }: OnboardingLinkProps) => {
  const { catalog, isLoading } = useOnboardingProgress();

  if (session?.userRole === "noc") {
    return null;
  }
  if (isLoading) {
    return null;
  }

  return (
    <ul className="space-y-0.5 p-1 pr-1">
      <li>
        <LinkWithIcon
          href="/onboarding"
          icon={HiOutlineSparkles}
          count={catalog.length || undefined}
          testId="onboarding-setup"
        >
          <Subtitle className="text-xs">Alert lifecycle</Subtitle>
        </LinkWithIcon>
      </li>
    </ul>
  );
};
