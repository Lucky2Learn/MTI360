import type { Metadata } from "next";
import type { ReactNode } from "react";

// Platform Administration (/platform): MTI 360 SaaS control plane.
// Route boundary (T00-08). Since T01-09B it holds two route groups
// (invisible in URLs): (auth) — the public platform authentication pages on
// the T16 template, outside the shell — and (console) — the guarded platform
// shell. Nothing under /platform is indexed.
export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

export default function PlatformLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return children;
}
