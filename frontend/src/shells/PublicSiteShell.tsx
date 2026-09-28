"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { ToastRegion } from "@/design-system/components";
import { WebsiteIcon } from "@/design-system/icons";
import { cx, focusRing } from "@/design-system/lib/cx";
import { ThemeSelector } from "@/design-system/theme/ThemeSelector";

import { MobileNavigation } from "./MobileNavigation";
import { isCurrentPage, type Navigation } from "./navigation";
import { MAIN_CONTENT_ID, SkipNavigation } from "./SkipNavigation";

import type { ReactNode } from "react";

// PublicSiteShell (T00-08): frame of the Tenant Public Website (/site) —
// public, mobile-first, no sidebar, account or notifications. Top navigation
// from the desktop breakpoint, the shared navigation drawer below it, and a
// footer with the appearance control. It carries no tenant identity or
// branding yet (Phase 14 resolves the tenant server-side from a verified
// domain); it is not the MTI 360 marketing website (ADR-0003, INC-26).

export type PublicSiteShellProps = {
  siteLabel: string;
  homeHref: string;
  navigation: Navigation;
  navigationLabel: string;
  children: ReactNode;
};

export function PublicSiteShell({
  siteLabel,
  homeHref,
  navigation,
  navigationLabel,
  children,
}: PublicSiteShellProps) {
  const pathname = usePathname() ?? homeHref;
  const items = navigation.flatMap((section) => section.items);

  return (
    <div className="flex min-h-dvh flex-col">
      <SkipNavigation />
      <header className="sticky top-0 z-(--z-sticky) border-b border-border-subtle bg-surface-primary">
        <div className="mx-auto flex h-16 w-full max-w-6xl items-center gap-2 px-2 tablet:px-6 desktop:px-8">
          <MobileNavigation
            experienceLabel={siteLabel}
            navigationLabel={navigationLabel}
            navigation={navigation}
            pathname={pathname}
          />
          <Link
            href={homeHref}
            className={cx(
              "flex min-h-control-lg items-center gap-2 rounded-md px-1 text-body font-bold text-text-primary tablet:min-h-control-md",
              focusRing,
            )}
          >
            <span
              aria-hidden="true"
              className="flex size-8 items-center justify-center rounded-md bg-surface-secondary text-accent-maritime"
            >
              <WebsiteIcon className="size-5" />
            </span>
            <span>
              {siteLabel}
              <span className="sr-only"> home</span>
            </span>
          </Link>
          <nav
            aria-label={navigationLabel}
            className="ml-auto hidden desktop:block"
          >
            <ul className="flex items-center gap-1">
              {items.map((item) => {
                const current = isCurrentPage(item, pathname);
                return (
                  <li key={item.id}>
                    <Link
                      href={item.href}
                      aria-current={current ? "page" : undefined}
                      className={cx(
                        "flex h-control-md items-center rounded-md px-3 text-body-sm text-text-primary underline-offset-8",
                        "transition-colors hover:bg-surface-hover motion-reduce:transition-none",
                        current &&
                          "font-semibold underline decoration-accent-maritime decoration-2",
                        focusRing,
                      )}
                    >
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>
        </div>
      </header>
      <main
        id={MAIN_CONTENT_ID}
        tabIndex={-1}
        className="flex min-w-0 flex-1 flex-col outline-none"
      >
        {children}
      </main>
      <footer className="border-t border-border-subtle bg-surface-secondary">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-8 tablet:flex-row tablet:items-start tablet:justify-between tablet:px-6 desktop:px-8">
          <p className="max-w-md text-body-sm text-text-secondary">
            Website preview. The institute&apos;s own name, branding and content
            are added when the public website is built.
          </p>
          <ThemeSelector />
        </div>
      </footer>
      <ToastRegion />
    </div>
  );
}
