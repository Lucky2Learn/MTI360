import { cx } from "@/design-system/lib/cx";

import {
  alignClasses,
  gapClasses,
  gridColumnClasses,
  gridSpanClasses,
  responsiveClasses,
  type CrossAlign,
  type Gap,
  type GridColumns,
  type GridSpan,
  type Responsive,
} from "./responsive";

import type { ReactNode } from "react";

// Grid and GridItem (T00-09; DESIGN-SYSTEM.md §81). Equal-width columns with
// a count per breakpoint, mobile-first:
//
//   <Grid columns={{ base: 1, tablet: 2, desktop: 4 }} gap="lg">
//
// Columns are minmax(0, 1fr) and every child may shrink below its content
// width, so long values wrap or truncate inside the cell instead of widening
// the page. GridItem spans columns (per breakpoint as well). Not a dashboard:
// screens decide what goes in the cells. Server-component compatible.

export type GridProps = {
  columns?: Responsive<GridColumns>;
  gap?: Gap;
  /** Vertical alignment of items in a row; stretch (equal height) by default. */
  align?: CrossAlign;
  as?: "div" | "section" | "ul" | "ol";
  id?: string;
  "aria-labelledby"?: string;
  "aria-label"?: string;
  children: ReactNode;
};

export function Grid({
  columns = 1,
  gap = "lg",
  align = "stretch",
  as: Element = "div",
  children,
  ...rest
}: GridProps) {
  return (
    <Element
      {...rest}
      className={cx(
        "grid min-w-0 *:min-w-0",
        responsiveClasses(columns, gridColumnClasses),
        gapClasses[gap],
        alignClasses[align],
      )}
    >
      {children}
    </Element>
  );
}

export type GridItemProps = {
  span?: Responsive<GridSpan>;
  as?: "div" | "li" | "section" | "article";
  id?: string;
  "aria-labelledby"?: string;
  "aria-label"?: string;
  children: ReactNode;
};

export function GridItem({
  span = 1,
  as: Element = "div",
  children,
  ...rest
}: GridItemProps) {
  return (
    <Element
      {...rest}
      className={cx("min-w-0", responsiveClasses(span, gridSpanClasses))}
    >
      {children}
    </Element>
  );
}
