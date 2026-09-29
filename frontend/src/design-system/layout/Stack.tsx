import { cx } from "@/design-system/lib/cx";

import {
  alignClasses,
  gapClasses,
  type CrossAlign,
  type Gap,
} from "./responsive";

import type { ReactNode } from "react";

// Stack (T00-09): vertical flow with a spacing token between children. Use it
// for page sections (gap "xl"/"2xl", which grow from tablet), card content and
// grouped fields. Spacing comes from the 4px scale only (responsive.ts).
// Server-component compatible.

export type StackProps = {
  gap?: Gap;
  /** Horizontal alignment of the children; stretch (full width) by default. */
  align?: CrossAlign;
  as?: "div" | "section" | "article" | "ul" | "ol";
  id?: string;
  "aria-labelledby"?: string;
  "aria-label"?: string;
  children: ReactNode;
};

export function Stack({
  gap = "md",
  align = "stretch",
  as: Element = "div",
  children,
  ...rest
}: StackProps) {
  return (
    <Element
      {...rest}
      className={cx(
        "flex min-w-0 flex-col",
        gapClasses[gap],
        alignClasses[align],
      )}
    >
      {children}
    </Element>
  );
}
