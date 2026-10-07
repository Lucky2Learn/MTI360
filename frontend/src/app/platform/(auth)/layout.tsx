import type { ReactNode } from "react";

// Platform authentication screens (T01-09B UI contract §4): /platform/login,
// /platform/forgot-password, /platform/reset-password,
// /platform/accept-invitation and /platform/session-ended, outside the
// platform shell. The route group is invisible in URLs. Each page renders the
// T16 AuthenticationTemplate with the "Platform administration" context;
// server entry checks are UX routing only — the platform API decides
// everything. MFA steps are in-memory steps of /platform/login (D9B-2).
export default function PlatformAuthLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return children;
}
