import { EXPERIENCE, ExperienceFrame } from "@/shells";

import type { Metadata } from "next";
import type { ReactNode } from "react";

// Tenant Application (/app): one Maritime Training Institute's workspace.
// Route boundary (T00-08). No authentication, authorization or tenant
// resolution happens here yet; later phases enforce access server-side at
// this boundary. Placeholder pages are not indexed.
export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

export default function TenantLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return (
    <ExperienceFrame experience={EXPERIENCE.TENANT}>{children}</ExperienceFrame>
  );
}
