import { THEME_PRE_PAINT_SCRIPT } from "@/design-system/theme/pre-paint";
import { ThemeProvider } from "@/design-system/theme/ThemeProvider";
import { fontVariables } from "@/design-system/typography/fonts";

import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

// Root layout (T00-02; design tokens, Inter and the Light/Dark/System theme
// since T00-06). Application shells are added in T00-08.
export const metadata: Metadata = {
  title: "MTI 360",
  description:
    "MTI 360 — Growth & Operations Platform for Maritime Training Institutes.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return (
    // suppressHydrationWarning: the pre-paint script sets data-theme and
    // color-scheme on <html> before React hydrates (this element only).
    <html lang="en" className={fontVariables} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_PRE_PAINT_SCRIPT }} />
      </head>
      <body>
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
