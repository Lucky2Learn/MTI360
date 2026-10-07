import { ForgotPasswordScreen } from "@/features/identity/ForgotPasswordScreen";

import type { Metadata } from "next";

// PAUTH-01 /platform/forgot-password (T01-09B UI contract §7): the AUTH-02
// screen on POST /platform/auth/password-reset. No entry check.
export const metadata: Metadata = {
  title: "Reset your password · MTI 360 Platform",
};

export default function PlatformForgotPasswordPage() {
  return <ForgotPasswordScreen realm="platform" />;
}
