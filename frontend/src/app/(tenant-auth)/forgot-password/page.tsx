import { ForgotPasswordScreen } from "@/features/identity/ForgotPasswordScreen";

import type { Metadata } from "next";

// AUTH-02 /forgot-password (T01-04 UI contract §8.2). No entry check:
// reachable when signed in, too.
export const metadata: Metadata = { title: "Reset your password · MTI 360" };

export default function ForgotPasswordPage() {
  return <ForgotPasswordScreen />;
}
