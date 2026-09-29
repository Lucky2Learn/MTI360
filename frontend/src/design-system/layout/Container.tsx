import { cx } from "@/design-system/lib/cx";

import type { ReactNode } from "react";

// Container (T00-09; DESIGN-SYSTEM.md §82–§83). Centres content, caps its
// width so text and forms are not stretched across large screens, and applies
// the page gutter (16px mobile → 24px tablet → 32px desktop). The widths are
// the content-width conventions every page uses (docs/architecture/layout.md):
//
//   narrow    48rem   focused forms, settings, single-task flows
//   standard  72rem   most pages and detail pages (default)
//   wide      80rem   dashboards, lists and data tables
//   full      none    workspaces that use the whole viewport (Kanban, inbox)
//
// Server-component compatible.

export type ContentWidth = "narrow" | "standard" | "wide" | "full";

export const contentWidthClasses: Record<ContentWidth, string> = {
  narrow: "max-w-3xl",
  standard: "max-w-6xl",
  wide: "max-w-7xl",
  full: "max-w-none",
};

/** Horizontal page gutter on the 4px grid (16 → 24 → 32px). */
export const pageGutterClasses = "px-4 tablet:px-6 desktop:px-8";

export type ContainerProps = {
  width?: ContentWidth;
  /** Apply the responsive page gutter (default). Disable inside an already padded region. */
  gutter?: boolean;
  as?: "div" | "section" | "header" | "footer";
  id?: string;
  "aria-labelledby"?: string;
  "aria-label"?: string;
  children: ReactNode;
};

export function Container({
  width = "standard",
  gutter = true,
  as: Element = "div",
  children,
  ...rest
}: ContainerProps) {
  return (
    <Element
      {...rest}
      data-width={width}
      className={cx(
        "mx-auto w-full min-w-0",
        contentWidthClasses[width],
        gutter && pageGutterClasses,
      )}
    >
      {children}
    </Element>
  );
}
