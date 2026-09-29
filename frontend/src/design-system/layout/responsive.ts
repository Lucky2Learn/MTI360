// Responsive layout vocabulary (T00-09; DESIGN-SYSTEM.md §20–§21).
//
// Breakpoints are the approved tiers from tokens/tailwind.css: mobile
// (390–767) is the base, then tablet (768), desktop (1024) and large (1440).
// Every class below is written out literally so Tailwind can find it in the
// source; never build a utility name with a template string.

export type Breakpoint = "base" | "tablet" | "desktop" | "large";

/** A value for all widths, or per breakpoint (mobile-first: each tier applies from its width up). */
export type Responsive<T> = T | Partial<Record<Breakpoint, T>>;

const BREAKPOINTS: Breakpoint[] = ["base", "tablet", "desktop", "large"];

function isPerBreakpoint<T extends string | number>(
  value: Responsive<T>,
): value is Partial<Record<Breakpoint, T>> {
  return typeof value === "object" && value !== null;
}

/** Resolves a responsive value to the classes of each tier that is set. */
export function responsiveClasses<T extends string | number>(
  value: Responsive<T>,
  classes: Record<Breakpoint, Record<T, string>>,
): string {
  if (!isPerBreakpoint(value)) return classes.base[value];
  return BREAKPOINTS.flatMap((tier) => {
    const tierValue = value[tier];
    return tierValue === undefined ? [] : [classes[tier][tierValue]];
  }).join(" ");
}

/**
 * Spacing between children, on the 4px grid (DESIGN-SYSTEM.md §20):
 * 2xs 4 (micro) · xs 8 (compact) · sm 12 (small) · md 16 (standard) ·
 * lg 24 (card/panel) · xl 24→32 (section) · 2xl 32→48 (major section).
 * xl and 2xl are compact on mobile and grow from the tablet breakpoint.
 */
export type Gap = "none" | "2xs" | "xs" | "sm" | "md" | "lg" | "xl" | "2xl";

export const gapClasses: Record<Gap, string> = {
  none: "gap-0",
  "2xs": "gap-1",
  xs: "gap-2",
  sm: "gap-3",
  md: "gap-4",
  lg: "gap-6",
  xl: "gap-6 tablet:gap-8",
  "2xl": "gap-8 tablet:gap-12",
};

/** Breakpoint below which a horizontal layout stacks vertically. */
export type StackBelow = "tablet" | "desktop";

export type CrossAlign = "start" | "center" | "end" | "stretch";

export const alignClasses: Record<CrossAlign | "baseline", string> = {
  start: "items-start",
  center: "items-center",
  end: "items-end",
  stretch: "items-stretch",
  baseline: "items-baseline",
};

export const alignFromClasses: Record<
  StackBelow,
  Record<CrossAlign | "baseline", string>
> = {
  tablet: {
    start: "tablet:items-start",
    center: "tablet:items-center",
    end: "tablet:items-end",
    stretch: "tablet:items-stretch",
    baseline: "tablet:items-baseline",
  },
  desktop: {
    start: "desktop:items-start",
    center: "desktop:items-center",
    end: "desktop:items-end",
    stretch: "desktop:items-stretch",
    baseline: "desktop:items-baseline",
  },
};

export const rowFromClasses: Record<StackBelow, string> = {
  tablet: "flex-col tablet:flex-row",
  desktop: "flex-col desktop:flex-row",
};

export type Justify = "start" | "center" | "end" | "between";

export const justifyClasses: Record<Justify, string> = {
  start: "justify-start",
  center: "justify-center",
  end: "justify-end",
  between: "justify-between",
};

/** Grid column counts (12 is the desktop conceptual grid, DESIGN-SYSTEM.md §81). */
export type GridColumns = 1 | 2 | 3 | 4 | 5 | 6 | 12;

export const gridColumnClasses: Record<
  Breakpoint,
  Record<GridColumns, string>
> = {
  base: {
    1: "grid-cols-1",
    2: "grid-cols-2",
    3: "grid-cols-3",
    4: "grid-cols-4",
    5: "grid-cols-5",
    6: "grid-cols-6",
    12: "grid-cols-12",
  },
  tablet: {
    1: "tablet:grid-cols-1",
    2: "tablet:grid-cols-2",
    3: "tablet:grid-cols-3",
    4: "tablet:grid-cols-4",
    5: "tablet:grid-cols-5",
    6: "tablet:grid-cols-6",
    12: "tablet:grid-cols-12",
  },
  desktop: {
    1: "desktop:grid-cols-1",
    2: "desktop:grid-cols-2",
    3: "desktop:grid-cols-3",
    4: "desktop:grid-cols-4",
    5: "desktop:grid-cols-5",
    6: "desktop:grid-cols-6",
    12: "desktop:grid-cols-12",
  },
  large: {
    1: "large:grid-cols-1",
    2: "large:grid-cols-2",
    3: "large:grid-cols-3",
    4: "large:grid-cols-4",
    5: "large:grid-cols-5",
    6: "large:grid-cols-6",
    12: "large:grid-cols-12",
  },
};

/** Columns a grid item spans; "full" spans every column of the grid. */
export type GridSpan =
  1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | "full";

export const gridSpanClasses: Record<Breakpoint, Record<GridSpan, string>> = {
  base: {
    1: "col-span-1",
    2: "col-span-2",
    3: "col-span-3",
    4: "col-span-4",
    5: "col-span-5",
    6: "col-span-6",
    7: "col-span-7",
    8: "col-span-8",
    9: "col-span-9",
    10: "col-span-10",
    11: "col-span-11",
    12: "col-span-12",
    full: "col-span-full",
  },
  tablet: {
    1: "tablet:col-span-1",
    2: "tablet:col-span-2",
    3: "tablet:col-span-3",
    4: "tablet:col-span-4",
    5: "tablet:col-span-5",
    6: "tablet:col-span-6",
    7: "tablet:col-span-7",
    8: "tablet:col-span-8",
    9: "tablet:col-span-9",
    10: "tablet:col-span-10",
    11: "tablet:col-span-11",
    12: "tablet:col-span-12",
    full: "tablet:col-span-full",
  },
  desktop: {
    1: "desktop:col-span-1",
    2: "desktop:col-span-2",
    3: "desktop:col-span-3",
    4: "desktop:col-span-4",
    5: "desktop:col-span-5",
    6: "desktop:col-span-6",
    7: "desktop:col-span-7",
    8: "desktop:col-span-8",
    9: "desktop:col-span-9",
    10: "desktop:col-span-10",
    11: "desktop:col-span-11",
    12: "desktop:col-span-12",
    full: "desktop:col-span-full",
  },
  large: {
    1: "large:col-span-1",
    2: "large:col-span-2",
    3: "large:col-span-3",
    4: "large:col-span-4",
    5: "large:col-span-5",
    6: "large:col-span-6",
    7: "large:col-span-7",
    8: "large:col-span-8",
    9: "large:col-span-9",
    10: "large:col-span-10",
    11: "large:col-span-11",
    12: "large:col-span-12",
    full: "large:col-span-full",
  },
};
