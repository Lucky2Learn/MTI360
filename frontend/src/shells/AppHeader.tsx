import Link from "next/link";

import { CompassIcon } from "@/design-system/icons";
import { cx, focusRing } from "@/design-system/lib/cx";

import type { ReactNode } from "react";

// AppHeader (T00-08): sticky application bar — MTI 360 identity, the current
// experience, and slots for the navigation trigger (below desktop) and the
// shell utilities (search, notifications, account). Stable 64px height. The
// experience label is hidden on mobile (the navigation drawer title repeats
// it) so the bar never overflows at 390px.

export type AppHeaderProps = {
  experienceLabel: string;
  homeHref: string;
  /** Navigation trigger shown before the identity. */
  navigationTrigger?: ReactNode;
  /** Utilities at the end of the bar. */
  actions?: ReactNode;
};

export function AppHeader({
  experienceLabel,
  homeHref,
  navigationTrigger,
  actions,
}: AppHeaderProps) {
  return (
    <header className="sticky top-0 z-(--z-sticky) flex h-16 items-center gap-2 border-b border-border-subtle bg-surface-primary px-2 tablet:gap-3 tablet:px-4">
      {navigationTrigger}
      <Link
        href={homeHref}
        className={cx(
          "flex min-h-control-lg shrink-0 items-center gap-2 rounded-md px-1 text-body font-bold text-text-primary tablet:min-h-control-md",
          focusRing,
        )}
      >
        <span
          aria-hidden="true"
          className="flex size-8 items-center justify-center rounded-md bg-brand-primary text-text-inverse"
        >
          <CompassIcon className="size-5" />
        </span>
        <span>
          MTI 360
          <span className="sr-only">{`, ${experienceLabel} home`}</span>
        </span>
      </Link>
      <span
        aria-hidden="true"
        className="hidden h-6 border-l border-border-default tablet:block"
      />
      <p className="hidden min-w-0 truncate text-body-sm font-medium text-text-secondary tablet:block">
        {experienceLabel}
      </p>
      {actions && (
        <div className="ml-auto flex shrink-0 items-center gap-1">
          {actions}
        </div>
      )}
    </header>
  );
}
