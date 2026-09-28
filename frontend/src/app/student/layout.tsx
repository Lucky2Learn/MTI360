import { EXPERIENCE, ExperienceFrame } from "@/shells";

import type { Metadata } from "next";
import type { ReactNode } from "react";

// Student Portal (/student): mobile-first student experience.
// Route boundary (T00-08). No authentication, authorization or tenant
// resolution happens here yet; later phases enforce access server-side at
// this boundary. Placeholder pages are not indexed.
export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

export default function StudentLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return (
    <ExperienceFrame experience={EXPERIENCE.STUDENT}>
      {children}
    </ExperienceFrame>
  );
}
