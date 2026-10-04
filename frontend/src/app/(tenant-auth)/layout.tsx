import type { Metadata } from "next";
import type { ReactNode } from "react";

// Tenant authentication screens (T01-09A; T01-04 UI contract §6): /login,
// /forgot-password, /reset-password, /accept-invitation, /select-institute,
// /select-campus and /session-ended, outside the /app shell. The route group
// is invisible in URLs. Each page renders the T16 AuthenticationTemplate;
// server entry checks are UX routing only — the API decides everything.
// Never indexed; no tenant branding before sign-in (S14).
export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

export default function TenantAuthLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return children;
}
