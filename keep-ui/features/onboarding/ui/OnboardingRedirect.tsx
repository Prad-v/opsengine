"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import { useOnboardingProgress } from "../model/useOnboardingProgress";

const LANDING_PATHS = ["/", "/incidents"];

export function OnboardingRedirect() {
  const router = useRouter();
  const pathname = usePathname() || "";
  const { data: session } = useSession();
  const { isLoading, shouldRedirectToWizard } = useOnboardingProgress();

  useEffect(() => {
    if (isLoading || !session) {
      return;
    }
    if (session.userRole === "noc") {
      return;
    }
    if (!LANDING_PATHS.includes(pathname)) {
      return;
    }
    if (!shouldRedirectToWizard) {
      return;
    }
    router.replace("/onboarding");
  }, [isLoading, pathname, router, session, shouldRedirectToWizard]);

  return null;
}
