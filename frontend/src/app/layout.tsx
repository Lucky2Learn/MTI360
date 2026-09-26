import type { Metadata } from "next";
import type { ReactNode } from "react";

// Minimal root layout (T00-02). Design tokens, fonts and the Light/Dark/System
// theme are introduced in T00-06; application shells in T00-08.
export const metadata: Metadata = {
  title: "MTI 360",
  description:
    "MTI 360 — Growth & Operations Platform for Maritime Training Institutes.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
