import { AcceptInvitationScreen } from "@/features/identity/AcceptInvitationScreen";

import type { Metadata } from "next";

// AUTH-06 /accept-invitation#token=… (T01-04 UI contract §8.4; D19). The
// token is in the URL fragment, which never reaches this server.
export const metadata: Metadata = { title: "Accept your invitation · MTI 360" };

export default function AcceptInvitationPage() {
  return <AcceptInvitationScreen />;
}
