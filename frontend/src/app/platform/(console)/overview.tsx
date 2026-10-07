"use client";

import { EmptyState } from "@/design-system/components";
import { CompassIcon, LockIcon } from "@/design-system/icons";
import { LowRecoveryCodesAlert } from "@/features/platform-identity/SignInSecurity";
import { usePlatformSession } from "@/lib/session/PlatformSessionProvider";
import { PageContainer, PageContent, PageHeader } from "@/shells";

// Platform Overview (T01-09B UI contract §8). No platform module ships in
// T01, so the page is an intentional empty state. A platform user without
// any effective permission (T01: every role other than Super Admin and
// Security / Audit Admin) is told so — without naming permissions or roles.
// The low recovery-codes warning (D9B-7) comes from the server session.

export function PlatformOverview() {
  const { session } = usePlatformSession();
  const nothingAssigned = session.permissions.size === 0;
  return (
    <PageContainer width="wide">
      <PageHeader title="Overview" />
      <PageContent>
        <div className="flex flex-col gap-6">
          <LowRecoveryCodesAlert withAction />
          {nothingAssigned ? (
            <EmptyState
              titleAs="h2"
              icon={LockIcon}
              title="No platform areas are assigned to your role yet"
              description="When a Super Admin gives your account access to an area, it appears in the navigation."
            />
          ) : (
            <EmptyState
              titleAs="h2"
              icon={CompassIcon}
              title="Your platform overview is empty for now"
              description="Sections appear here as platform modules become available to your account."
            />
          )}
        </div>
      </PageContent>
    </PageContainer>
  );
}
