import { TenantSignInSecurity } from "@/features/identity/TenantSignInSecurity";
import { ACCOUNT_SECURITY } from "@/lib/session/routes";
import { requireReadyTenantSession } from "@/lib/session/server";
import { SessionSync } from "@/lib/session/SessionProvider";
import { PageContainer, PageContent, PageHeader } from "@/shells";

import type { Metadata } from "next";

// Tenant AUTH-04 Sign-in security, /app/account/security (T01-09C UI
// contract; D9C-1). The signed-in member's own two-step verification —
// personal, so any ready tenant session may open it (the T01-06 session MFA
// endpoints need a session, not a permission). Reached from the account
// menu, not the navigation. The server session gate runs first on every
// request; the API authorizes every change.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Sign-in security · Tenant Application · MTI 360",
};

export default async function AccountSecurityPage() {
  const session = await requireReadyTenantSession(ACCOUNT_SECURITY);
  return (
    <>
      <SessionSync session={session} />
      <PageContainer>
        <PageHeader
          title="Sign-in security"
          description="Your MTI 360 account and two-step verification."
        />
        <PageContent>
          <TenantSignInSecurity />
        </PageContent>
      </PageContainer>
    </>
  );
}
