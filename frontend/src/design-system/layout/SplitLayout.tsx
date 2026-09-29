import { cx } from "@/design-system/lib/cx";

import {
  gapClasses,
  gridColumnClasses,
  gridSpanClasses,
  type Gap,
  type GridColumns,
  type GridSpan,
} from "./responsive";

import type { ReactNode } from "react";

// SplitLayout (T00-09): primary and secondary content side by side from a
// breakpoint, stacked below it — detail pages (record + summary), forms with
// guidance, settings with context.
//
//   desktop  ┌──────────────────────┬───────────┐   mobile  ┌───────────┐
//            │ primary              │ secondary │           │ primary   │
//            └──────────────────────┴───────────┘           ├───────────┤
//                                                           │ secondary │
//                                                           └───────────┘
//
// The DOM order is the stacked (reading and focus) order. `secondaryPosition
// = "start"` places the secondary column first — on the left in a row and on
// top when stacked — so the visual order never differs from the DOM order.
// Server-component compatible.

export type SplitRatio = "1:1" | "2:1" | "3:1";
export type SplitBreakpoint = "tablet" | "desktop" | "large";

const ratios: Record<
  SplitRatio,
  { columns: GridColumns; primary: GridSpan; secondary: GridSpan }
> = {
  "1:1": { columns: 2, primary: 1, secondary: 1 },
  "2:1": { columns: 3, primary: 2, secondary: 1 },
  "3:1": { columns: 4, primary: 3, secondary: 1 },
};

export type SplitLayoutProps = {
  primary: ReactNode;
  secondary: ReactNode;
  /** Width of primary : secondary once side by side. */
  ratio?: SplitRatio;
  /** The columns sit side by side from this breakpoint; stacked below it. */
  stackBelow?: SplitBreakpoint;
  /** Secondary column after (default) or before the primary column. */
  secondaryPosition?: "end" | "start";
  gap?: Gap;
};

export function SplitLayout({
  primary,
  secondary,
  ratio = "2:1",
  stackBelow = "desktop",
  secondaryPosition = "end",
  gap = "lg",
}: SplitLayoutProps) {
  const {
    columns,
    primary: primarySpan,
    secondary: secondarySpan,
  } = ratios[ratio];
  const primaryColumn = (
    <div
      data-slot="primary"
      className={cx("min-w-0", gridSpanClasses[stackBelow][primarySpan])}
    >
      {primary}
    </div>
  );
  const secondaryColumn = (
    <div
      data-slot="secondary"
      className={cx("min-w-0", gridSpanClasses[stackBelow][secondarySpan])}
    >
      {secondary}
    </div>
  );

  return (
    <div
      data-ratio={ratio}
      data-stack-below={stackBelow}
      className={cx(
        "grid min-w-0 grid-cols-1 items-start",
        gridColumnClasses[stackBelow][columns],
        gapClasses[gap],
      )}
    >
      {secondaryPosition === "start" ? secondaryColumn : primaryColumn}
      {secondaryPosition === "start" ? primaryColumn : secondaryColumn}
    </div>
  );
}
