import { cx } from "@/design-system/lib/cx";

import type { ReactNode } from "react";

// PageContainer / PageContent (T00-08): the content column inside the shell.
// Responsive horizontal padding (16 → 24 → 32px) and a maximum width so large
// screens (1440+) do not stretch text and forms across the viewport. The full
// responsive grid system is T00-09; this is only what the shell needs.

export type PageWidth = "standard" | "wide" | "full";

const widths: Record<PageWidth, string> = {
  standard: "max-w-6xl",
  wide: "max-w-7xl",
  full: "max-w-none",
};

export type PageContainerProps = {
  /** standard: most pages; wide: dashboards and tables; full: workspaces. */
  width?: PageWidth;
  children: ReactNode;
};

export function PageContainer({
  width = "standard",
  children,
}: PageContainerProps) {
  return (
    <div
      data-page-width={width}
      className={cx(
        "mx-auto flex w-full min-w-0 flex-col gap-6 px-4 py-6 tablet:gap-8 tablet:px-6 tablet:py-8 desktop:px-8",
        widths[width],
      )}
    >
      {children}
    </div>
  );
}

/** Vertical stack for the sections below the page header. */
export function PageContent({ children }: { children: ReactNode }) {
  return <div className="flex min-w-0 flex-col gap-6">{children}</div>;
}
