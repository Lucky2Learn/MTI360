import { ResetPasswordScreen } from "@/features/identity/ResetPasswordScreen";

import type { Metadata } from "next";

// PAUTH-02 /platform/reset-password#token=… (T01-09B UI contract §7). The
// token is in the URL fragment, which never reaches this server; the page
// reads it in the browser and removes it from the address bar at once. The
// link path is fixed by the backend email template.
export const metadata: Metadata = {
  title: "Choose a new password · MTI 360 Platform",
};

export default function PlatformResetPasswordPage() {
  return <ResetPasswordScreen realm="platform" />;
}
