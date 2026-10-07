"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState, useSyncExternalStore, type ReactNode } from "react";

import { Alert, Button, LoadingRegion } from "@/design-system/components";
import type { MenuAction } from "@/design-system/components";
import {
  CompassIcon,
  InstituteIcon,
  LockIcon,
  SpinnerIcon,
} from "@/design-system/icons";
import {
  campusLabel,
  CampusSwitchDialog,
  CampusSwitcherTrigger,
} from "@/features/identity/CampusSwitcher";
import {
  InstituteSwitchDialog,
  TenantContextTrigger,
} from "@/features/identity/TenantContext";
import type { SessionWire } from "@/lib/api/types";
import { filterNavigation } from "@/lib/authz/navigation";
import { reloadDocument } from "@/lib/session/document";
import { ACCOUNT_SECURITY } from "@/lib/session/routes";
import { monogram, type Session } from "@/lib/session/session";
import {
  TenantSessionProvider,
  useTenantSession,
} from "@/lib/session/SessionProvider";
import { EXPERIENCE, ExperienceFrame, getExperience } from "@/shells";

// Tenant Application frame (T01-09A). Composes the shell with the server
// session: permission-filtered navigation (NAV-01/02), the institute context
// and campus switcher (tablet and up in the header; on mobile as account menu
// items), the account menu header (SESSION-01), "Sign-in security" (the
// member's own two-step verification, T01-09C D9C-1) and sign-out (J9). Everything
// here is UX; the /app page and the API decide access.

const BELOW_TABLET = "(max-width: 47.99rem)";

function subscribeBelowTablet(onChange: () => void) {
  if (typeof window.matchMedia !== "function") return () => undefined;
  const query = window.matchMedia(BELOW_TABLET);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

function useBelowTablet(): boolean {
  return useSyncExternalStore(
    subscribeBelowTablet,
    () =>
      typeof window.matchMedia === "function" &&
      window.matchMedia(BELOW_TABLET).matches,
    () => false,
  );
}

function AccountHeader({ session }: { session: Session }) {
  return (
    <>
      <p className="font-semibold break-words text-text-primary">
        {session.user.displayName}
      </p>
      <p className="break-all text-text-secondary">{session.user.email}</p>
      {session.activeInstitute && (
        <p className="break-words text-text-primary">
          {session.activeInstitute.name}
        </p>
      )}
      <p className="break-words text-text-secondary">
        {session.roles.length > 0
          ? `Roles: ${session.roles.map((role) => role.name).join(", ")}`
          : "No role assigned in this institute"}
      </p>
    </>
  );
}

type OpenDialog = "institute" | "campus" | null;

function TenantShell({
  showUnreleased,
  children,
}: {
  showUnreleased: boolean;
  children: ReactNode;
}) {
  const router = useRouter();
  const { session, signOut, changedElsewhere } = useTenantSession();
  const belowTablet = useBelowTablet();
  const [dialog, setDialog] = useState<OpenDialog>(null);
  const [signingOut, setSigningOut] = useState(false);

  const navigation = useMemo(
    () =>
      filterNavigation(getExperience(EXPERIENCE.TENANT).navigation, {
        permissions: session.permissions,
        showUnreleased,
      }),
    [session.permissions, showUnreleased],
  );

  const menuItems: MenuAction[] = [
    ...(belowTablet
      ? [
          ...(session.institutes.length > 1
            ? [
                {
                  id: "institute",
                  label: "Institute",
                  description: session.activeInstitute?.name,
                  icon: InstituteIcon,
                },
              ]
            : []),
          ...(session.campusOptions.length > 1
            ? [
                {
                  id: "campus",
                  label: "Campus",
                  description: campusLabel(session),
                  icon: CompassIcon,
                },
              ]
            : []),
        ]
      : []),
    { id: "security", label: "Sign-in security", icon: LockIcon },
  ];

  const startSignOut = () => {
    setSigningOut(true);
    void signOut();
  };

  return (
    <>
      <ExperienceFrame
        experience={EXPERIENCE.TENANT}
        session={{
          navigation,
          account: {
            name: session.user.displayName,
            detail: session.user.email,
            initials: monogram(session.user.displayName),
          },
          headerContext: (
            <div className="hidden min-w-0 items-center gap-2 tablet:flex">
              <TenantContextTrigger onOpen={() => setDialog("institute")} />
              <CampusSwitcherTrigger onOpen={() => setDialog("campus")} />
            </div>
          ),
          accountSession: {
            header: <AccountHeader session={session} />,
            items: menuItems,
            onItemAction: (id) => {
              if (id === "institute" || id === "campus") setDialog(id);
              if (id === "security") router.push(ACCOUNT_SECURITY);
            },
            onSignOut: startSignOut,
          },
        }}
      >
        {changedElsewhere && (
          <div className="px-4 pt-4 tablet:px-6 desktop:px-8">
            <Alert
              tone="info"
              title="You switched institute or campus in another tab."
              action={
                <Button variant="secondary" size="sm" onPress={reloadDocument}>
                  Reload
                </Button>
              }
            />
          </div>
        )}
        {children}
      </ExperienceFrame>
      <InstituteSwitchDialog
        isOpen={dialog === "institute"}
        onOpenChange={(open) => setDialog(open ? "institute" : null)}
      />
      <CampusSwitchDialog
        isOpen={dialog === "campus"}
        onOpenChange={(open) => setDialog(open ? "campus" : null)}
      />
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

export type TenantFrameProps = {
  session: SessionWire;
  /** UNRELEASED pages exist in this environment (development, test). */
  showUnreleased: boolean;
  children: ReactNode;
};

export function TenantFrame({
  session,
  showUnreleased,
  children,
}: TenantFrameProps) {
  return (
    <TenantSessionProvider initialSession={session}>
      <TenantShell showUnreleased={showUnreleased}>{children}</TenantShell>
    </TenantSessionProvider>
  );
}
