import { cx } from "@/design-system/lib/cx";

import {
  alignClasses,
  alignFromClasses,
  gapClasses,
  justifyClasses,
  rowFromClasses,
  type CrossAlign,
  type Gap,
  type Justify,
  type StackBelow,
} from "./responsive";

import type { ReactNode } from "react";

// Inline (T00-09): horizontal flow for action buttons, filter controls,
// metadata and badges. Children wrap onto new lines instead of overflowing
// (each child is capped at the row width), or — with `stackBelow` — stack
// full width below a breakpoint and sit in a row from it. Direction-neutral
// (flex + gap), so it mirrors correctly in a future RTL layout.
// Server-component compatible.

export type InlineProps = {
  gap?: Gap;
  align?: CrossAlign | "baseline";
  justify?: Justify;
  /** Wrap children onto new lines when they do not fit (default). */
  wrap?: boolean;
  /** Stack children vertically (full width) below this breakpoint. */
  stackBelow?: StackBelow;
  as?: "div" | "ul" | "ol";
  id?: string;
  "aria-labelledby"?: string;
  "aria-label"?: string;
  children: ReactNode;
};

export function Inline({
  gap = "sm",
  align = "center",
  justify = "start",
  wrap = true,
  stackBelow,
  as: Element = "div",
  children,
  ...rest
}: InlineProps) {
  return (
    <Element
      {...rest}
      data-stack-below={stackBelow}
      className={cx(
        "flex min-w-0 *:min-w-0 *:max-w-full",
        stackBelow
          ? cx(
              rowFromClasses[stackBelow],
              "items-stretch",
              alignFromClasses[stackBelow][align],
            )
          : cx("flex-row", alignClasses[align]),
        wrap ? "flex-wrap" : "flex-nowrap",
        gapClasses[gap],
        justifyClasses[justify],
      )}
    >
      {children}
    </Element>
  );
}
