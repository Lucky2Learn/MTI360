import { cx } from "@/design-system/lib/cx";

import type { ReactNode } from "react";

// Show (T00-09): the one convention for rendering different presentations at
// different widths, e.g. a compact summary on mobile and a full panel from
// desktop. Pure CSS (display: none / contents) — no window.innerWidth or
// resize listeners, so server and client render the same markup and there is
// no hydration mismatch or layout jump. The wrapper uses display: contents,
// so it does not disturb the parent's flex or grid layout.
//
//   <Show from="desktop">…</Show>                visible at 1024px and wider
//   <Show below="tablet">…</Show>                visible below 768px
//   <Show from="tablet" below="desktop">…</Show> visible at 768–1023px
//
// Hidden content is removed from the accessibility tree, so every width must
// still offer the same information and actions in some form: use Show for
// alternative presentations, never to drop essential content on mobile.
// Server-component compatible.

export type ShowBreakpoint = "tablet" | "desktop" | "large";

const fromClasses: Record<ShowBreakpoint, string> = {
  tablet: "tablet:contents",
  desktop: "desktop:contents",
  large: "large:contents",
};

const belowClasses: Record<ShowBreakpoint, string> = {
  tablet: "tablet:hidden",
  desktop: "desktop:hidden",
  large: "large:hidden",
};

export type ShowProps = {
  /** Visible from this breakpoint up. */
  from?: ShowBreakpoint;
  /** Visible below this breakpoint. */
  below?: ShowBreakpoint;
  as?: "div" | "span";
  children: ReactNode;
};

export function Show({
  from,
  below,
  as: Element = "div",
  children,
}: ShowProps) {
  return (
    <Element
      data-show-from={from}
      data-show-below={below}
      className={cx(
        from ? "hidden" : "contents",
        from && fromClasses[from],
        below && belowClasses[below],
      )}
    >
      {children}
    </Element>
  );
}
