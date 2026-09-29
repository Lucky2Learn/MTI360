import {
  contentWidthClasses,
  pageGutterClasses,
  type ContentWidth,
} from "@/design-system/layout";
import { cx } from "@/design-system/lib/cx";

import type { ReactNode } from "react";

// PageContainer / PageContent (T00-08; widths and gutter shared with the
// T00-09 layout Container): the content column inside the shell. Responsive
// horizontal padding (16 → 24 → 32px) and a maximum width so large screens
// (1440+) do not stretch text and forms across the viewport. Content-width
// conventions: docs/architecture/layout.md.

export type PageWidth = ContentWidth;

export type PageContainerProps = {
  /**
   * narrow: focused forms and settings; standard: most pages and detail
   * pages; wide: dashboards and tables; full: workspaces.
   */
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
        "mx-auto flex w-full min-w-0 flex-col gap-6 py-6 tablet:gap-8 tablet:py-8",
        pageGutterClasses,
        contentWidthClasses[width],
      )}
    >
      {children}
    </div>
  );
}

/** Vertical stack for the sections below the page header (24 → 32px apart). */
export function PageContent({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-6 tablet:gap-8">{children}</div>
  );
}
