"use client";

import { cx, focusRing } from "@/design-system/lib/cx";

import type { MouseEvent } from "react";

// SkipNavigation (T00-08; WCAG 2.4.1 Bypass Blocks): the first focusable
// element of every shell. Visually hidden until it receives keyboard focus;
// activating it moves focus to the main content (which has tabIndex=-1), so
// the next Tab continues from there. Focus is moved explicitly rather than
// through the URL hash, so the address stays clean and bookmarkable.

export const MAIN_CONTENT_ID = "main-content";

export type SkipNavigationProps = {
  targetId?: string;
  label?: string;
};

export function SkipNavigation({
  targetId = MAIN_CONTENT_ID,
  label = "Skip to content",
}: SkipNavigationProps) {
  const skip = (event: MouseEvent<HTMLAnchorElement>) => {
    const target = document.getElementById(targetId);
    if (!target) return;
    event.preventDefault();
    target.focus();
    target.scrollIntoView?.({ block: "start" });
  };

  return (
    <a
      href={`#${targetId}`}
      onClick={skip}
      className={cx(
        "sr-only rounded-md bg-surface-elevated text-body-sm font-semibold text-text-primary shadow-lg",
        // not-sr-only resets padding, so the focused padding is restated.
        "focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-(--z-toast) focus:px-4 focus:py-3",
        focusRing,
      )}
    >
      {label}
    </a>
  );
}
