"use client";

import { useHydratedSession as useSession } from "@/shared/lib/hooks/useHydratedSession";
import { ChangePasswordModal } from "@/components/navbar/ChangePasswordModal";
import { useConfig } from "utils/hooks/useConfig";
import { AuthType } from "@/utils/authenticationType";

/**
 * Blocks the UI with a non-dismissible password change dialog when the
 * signed-in DB user still has mustChangePassword set (e.g. first login with
 * default admin/admin credentials).
 */
export function ForcePasswordChangeGate() {
  const { data: session, update } = useSession();
  const { data: config } = useConfig();

  const isDbAuth = config?.AUTH_TYPE === AuthType.DB;
  const mustChangePassword = Boolean(
    isDbAuth &&
      (session?.mustChangePassword || session?.user?.mustChangePassword)
  );

  if (!mustChangePassword) {
    return null;
  }

  return (
    <ChangePasswordModal
      isOpen={true}
      forced={true}
      onClose={() => {}}
      onSuccess={async () => {
        await update({ mustChangePassword: false });
      }}
    />
  );
}
