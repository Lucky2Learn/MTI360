"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState, type ReactNode } from "react";

import { LoadingRegion } from "@/design-system/components";
import { LockIcon, SpinnerIcon } from "@/design-system/icons";
import { StepUpDialog } from "@/features/platform-identity/StepUpDialog";
import type { PlatformSessionWire } from "@/lib/api/types";
import { filterNavigation } from "@/lib/authz/navigation";
import { PLATFORM_PROFILE } from "@/lib/session/platform-routes";
import {
  platformRoleLabel,
  type PlatformSession,
} from "@/lib/session/platform-session";
import {
  PlatformSessionProvider,
  usePlatformSession,
} from "@/lib/session/PlatformSessionProvider";
import { monogram } from "@/lib/session/session";
import { EXPERIENCE, ExperienceFrame, getExperience } from "@/shells";

// Platform console frame (T01-09B UI contract §8). Composes the platform
// shell with the server session: permission-filtered navigation, the account
// menu header (name, email, roles — display only), "Sign-in security",
// Preferences, sign-out and the step-up dialog (PAUTH-07). No institute or
// campus controls: the platform realm has no tenant. Everything here is UX;
// the pages and the platform API decide access.

function AccountHeader({ session }: { session: PlatformSession }) {
  return (
    <>
      <p className="font-semibold break-words text-text-primary">
        {session.user.displayName}
      </p>
      <p className="break-all text-text-secondary">{session.user.email}</p>
      <p className="break-words text-text-secondary">
        {session.roles.length > 0
          ? `Roles: ${session.roles.map(platformRoleLabel).join(", ")}`
          : "No platform role assigned"}
      </p>
    </>
  );
}

function PlatformShell({
  showUnreleased,
  children,
}: {
  showUnreleased: boolean;
  children: ReactNode;
}) {
  const router = useRouter();
  const { session, signOut } = usePlatformSession();
  const [signingOut, setSigningOut] = useState(false);

  const navigation = useMemo(
    () =>
      filterNavigation(getExperience(EXPERIENCE.PLATFORM).navigation, {
        permissions: session.permissions,
        showUnreleased,
      }),
    [session.permissions, showUnreleased],
  );

  const startSignOut = () => {
    setSigningOut(true);
    void signOut();
  };

  return (
    <>
      <ExperienceFrame
        experience={EXPERIENCE.PLATFORM}
        session={{
          navigation,
          account: {
            name: session.user.displayName,
            detail: session.user.email,
            initials: monogram(session.user.displayName),
          },
          accountSession: {
            header: <AccountHeader session={session} />,
            items: [
              { id: "security", label: "Sign-in security", icon: LockIcon },
            ],
            onItemAction: (id) => {
              if (id === "security") router.push(PLATFORM_PROFILE);
            },
            onSignOut: startSignOut,
            hideUnavailable: true,
          },
        }}
      >
        {children}
      </ExperienceFrame>
      <StepUpDialog />
      {signingOut && (
        <div className="fixed inset-0 z-(--z-modal) flex items-center justify-center bg-background-primary">
          <LoadingRegion label="Signing out">
            <SpinnerIcon
              aria-hidden="true"
              className="size-8 text-text-secondary motion-safe:animate-spin"
            />
          </LoadingRegion>
        </div>
      )}
    </>
  );
}

export type PlatformFrameProps = {
  session: PlatformSessionWire;
  /** UNRELEASED pages exist in this environment (development). */
  showUnreleased: boolean;
  children: ReactNode;
};

export function PlatformFrame({
  session,
  showUnreleased,
  children,
}: PlatformFrameProps) {
  return (
    <PlatformSessionProvider initialSession={session}>
      <PlatformShell showUnreleased={showUnreleased}>{children}</PlatformShell>
    </PlatformSessionProvider>
  );
}
