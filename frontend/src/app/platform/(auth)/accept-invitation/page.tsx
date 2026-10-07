import { PlatformAcceptInvitationScreen } from "@/features/platform-identity/PlatformAcceptInvitationScreen";

import type { Metadata } from "next";

// PAUTH-03 /platform/accept-invitation#token=… (T01-09B UI contract §7). The
// token stays in the URL fragment (never sent to this server); the link path
// is fixed by the backend invitation email.
export const metadata: Metadata = {
  title: "Accept your invitation · MTI 360 Platform",
};

export default function PlatformAcceptInvitationPage() {
  return <PlatformAcceptInvitationScreen />;
}
