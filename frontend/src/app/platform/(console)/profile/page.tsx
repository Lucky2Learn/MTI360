import { SignInSecurity } from "@/features/platform-identity/SignInSecurity";
import { PLATFORM_PROFILE } from "@/lib/session/platform-routes";
import { requirePlatformSession } from "@/lib/session/platform-server";
import { PlatformSessionSync } from "@/lib/session/PlatformSessionProvider";
import { PageContainer, PageContent, PageHeader } from "@/shells";

import type { Metadata } from "next";

// Partial PLAT-52 /platform/profile — Sign-in security (T01-09B UI contract
// §10; D9B-8 accepted). Any full platform session may see its own sign-in
// security (requirement ALWAYS); the regeneration action is authorized by
// the API (step-up). Reached from the account menu.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Sign-in security · Platform Administration · MTI 360",
};

export default async function PlatformProfilePage() {
  const session = await requirePlatformSession(PLATFORM_PROFILE);
  return (
    <>
      <PlatformSessionSync session={session} />
      <PageContainer>
        <PageHeader
          title="Sign-in security"
          description="Your platform account and two-step verification."
        />
        <PageContent>
          <SignInSecurity />
        </PageContent>
      </PageContainer>
    </>
  );
}
