import { cx } from "@/design-system/lib/cx";

import type { ReactNode } from "react";

// ActionBar (T00-09; DESIGN-SYSTEM.md §84): the action area of a form,
// section or panel. Put the primary action LAST in the DOM:
//
//   tablet+   [Cancel] [Save draft] [Submit]        (row, wraps, aligned)
//   mobile    [Submit]                             (full width, stacked,
//             [Save draft]                          primary on top, 44px
//             [Cancel]                              controls from tokens)
//
// The mobile order is the established MTI 360 convention (PageHeader and the
// 07B form example): the primary action is the first thing under the thumb.
// Buttons keep their own size; nothing is shrunk to fit. Server-component
// compatible.

export type ActionBarAlign = "start" | "end" | "between";

const alignClasses: Record<ActionBarAlign, string> = {
  start: "tablet:justify-start",
  end: "tablet:justify-end",
  between: "tablet:justify-between",
};

export type ActionBarProps = {
  align?: ActionBarAlign;
  /** Separate the actions from the content above with a subtle rule. */
  divider?: boolean;
  "aria-label"?: string;
  children: ReactNode;
};

export function ActionBar({
  align = "end",
  divider = false,
  children,
  ...rest
}: ActionBarProps) {
  return (
    <div
      {...rest}
      role={rest["aria-label"] ? "group" : undefined}
      className={cx(
        "flex min-w-0 flex-col-reverse gap-2 tablet:flex-row tablet:flex-wrap tablet:items-center",
        alignClasses[align],
        divider && "border-t border-border-subtle pt-4",
      )}
    >
      {children}
    </div>
  );
}
