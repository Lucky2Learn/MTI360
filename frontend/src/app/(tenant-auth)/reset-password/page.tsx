import { ResetPasswordScreen } from "@/features/identity/ResetPasswordScreen";

import type { Metadata } from "next";

// AUTH-03 /reset-password#token=… (T01-04 UI contract §8.3). The token is in
// the URL fragment, which never reaches this server; the page reads it in
// the browser and removes it from the address bar at once.
export const metadata: Metadata = { title: "Choose a new password · MTI 360" };

export default function ResetPasswordPage() {
  return <ResetPasswordScreen />;
}
