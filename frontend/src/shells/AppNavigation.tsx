"use client";

import Link from "next/link";
import { useId, useState } from "react";

import { ChevronDownIcon } from "@/design-system/icons";
import { cx, focusRing } from "@/design-system/lib/cx";

import {
  findTrail,
  isCurrentPage,
  type NavItem,
  type Navigation,
} from "./navigation";

// AppNavigation (T00-08): configuration-driven navigation list used by the
// desktop sidebar and the mobile navigation drawer. Semantic <nav> with
// labelled lists; native links, so Tab/Shift+Tab and Enter work everywhere and
// links stay bookmarkable. The current page carries aria-current="page" and is
// marked by weight and an indicator bar, not colour alone. Nested items sit
// under a disclosure button (aria-expanded/aria-controls); the branch that
// contains the current page opens automatically.
//
// Display modes:
// - "full": labels, section headings and nested items (drawer, desktop);
// - "rail": icons only; labels stay available to assistive technology;
// - "auto": rail on tablet, full from the desktop breakpoint.

export type NavigationDisplay = "full" | "rail" | "auto";

const labelVisibility: Record<NavigationDisplay, string> = {
  full: "",
  rail: "sr-only",
  auto: "sr-only desktop:not-sr-only",
};

// Tailwind's not-sr-only resets padding, so visible headings restate theirs.
const headingLayout: Record<NavigationDisplay, string> = {
  full: "px-3 pb-1",
  rail: "sr-only",
  auto: "sr-only desktop:not-sr-only desktop:px-3 desktop:pb-1",
};

const inlineFullOnly: Record<NavigationDisplay, string> = {
  full: "",
  rail: "hidden",
  auto: "hidden desktop:inline",
};

const fullOnly: Record<NavigationDisplay, string> = {
  full: "",
  rail: "hidden",
  auto: "hidden desktop:flex",
};

const itemLayout: Record<NavigationDisplay, string> = {
  full: "justify-start px-3",
  rail: "justify-center px-0",
  auto: "justify-center px-0 desktop:justify-start desktop:px-3",
};

export type AppNavigationProps = {
  /** Accessible name of the navigation landmark, e.g. "Platform navigation". */
  label: string;
  navigation: Navigation;
  pathname: string;
  display?: NavigationDisplay;
  /** Called after a link is activated (the drawer closes itself). */
  onNavigate?: () => void;
};

export function AppNavigation({
  label,
  navigation,
  pathname,
  display = "full",
  onNavigate,
}: AppNavigationProps) {
  const trail = findTrail(navigation, pathname);

  return (
    <nav aria-label={label} className="flex flex-col gap-4">
      {navigation.map((section) => (
        <NavigationSection
          key={section.id}
          heading={section.label}
          items={section.items}
          trail={trail}
          pathname={pathname}
          display={display}
          onNavigate={onNavigate}
        />
      ))}
    </nav>
  );
}

type SectionProps = {
  heading?: string;
  items: NavItem[];
  trail: NavItem[];
  pathname: string;
  display: NavigationDisplay;
  onNavigate?: () => void;
};

function NavigationSection({ heading, items, ...rest }: SectionProps) {
  const headingId = useId();
  return (
    <div className="flex flex-col gap-1">
      {heading && (
        <p
          id={headingId}
          className={cx(
            "text-caption-sm font-semibold tracking-wide text-text-muted uppercase",
            headingLayout[rest.display],
          )}
        >
          {heading}
        </p>
      )}
      <ul
        aria-labelledby={heading ? headingId : undefined}
        className="flex flex-col gap-1"
      >
        {items.map((item) => (
          <NavigationItem key={item.id} item={item} depth={0} {...rest} />
        ))}
      </ul>
    </div>
  );
}

type ItemProps = Omit<SectionProps, "heading" | "items"> & {
  item: NavItem;
  depth: 0 | 1;
};

function NavigationItem({
  item,
  depth,
  trail,
  pathname,
  display,
  onNavigate,
}: ItemProps) {
  const childListId = useId();
  const inTrail = trail.includes(item);
  const isCurrent = isCurrentPage(item, pathname);
  const hasChildren = depth === 0 && Boolean(item.children?.length);
  // Open when the user opened it; otherwise when it contains the current page.
  const [userExpanded, setUserExpanded] = useState<boolean | null>(null);
  const expanded = userExpanded ?? inTrail;
  const Icon = item.icon;
  // Nested items are never shown in the rail, so they always use full layout.
  const itemDisplay: NavigationDisplay = depth === 0 ? display : "full";

  return (
    <li className="flex flex-col gap-1">
      <div className="flex items-center gap-1">
        <Link
          href={item.href}
          aria-current={isCurrent ? "page" : undefined}
          onClick={onNavigate}
          className={cx(
            "relative flex min-h-control-lg min-w-0 flex-1 items-center gap-3 rounded-md text-body-sm text-text-primary tablet:min-h-control-md",
            "transition-colors hover:bg-surface-hover motion-reduce:transition-none",
            focusRing,
            depth === 1 ? "justify-start pr-3 pl-12" : itemLayout[display],
            inTrail && "font-semibold",
            isCurrent && "bg-surface-selected",
          )}
        >
          {inTrail && (
            <span
              aria-hidden="true"
              className="absolute inset-y-2 left-0 w-1 rounded-full bg-accent-maritime"
            />
          )}
          {Icon ? (
            <Icon aria-hidden="true" className="size-5 shrink-0" />
          ) : (
            depth === 0 && (
              <span
                aria-hidden="true"
                className={cx(
                  "flex size-5 shrink-0 items-center justify-center text-caption-sm font-semibold",
                  display === "full" && "hidden",
                  display === "auto" && "desktop:hidden",
                )}
              >
                {item.label.slice(0, 2)}
              </span>
            )
          )}
          <span
            className={cx(
              "min-w-0 flex-1 truncate",
              labelVisibility[itemDisplay],
            )}
          >
            {item.label}
          </span>
          {item.badge && (
            <>
              <span
                aria-hidden="true"
                className={cx(
                  "rounded-full bg-surface-secondary px-2 text-caption-sm font-semibold text-text-primary",
                  inlineFullOnly[itemDisplay],
                )}
              >
                {item.badge.count}
              </span>
              <span className="sr-only">{`, ${item.badge.label}`}</span>
            </>
          )}
        </Link>
        {hasChildren && (
          <button
            type="button"
            aria-expanded={expanded}
            aria-controls={childListId}
            aria-label={`${item.label} pages`}
            onClick={() => setUserExpanded(!expanded)}
            className={cx(
              "size-control-md shrink-0 cursor-pointer items-center justify-center rounded-md text-text-secondary",
              "transition-colors hover:bg-surface-hover motion-reduce:transition-none",
              focusRing,
              display === "full" ? "flex" : fullOnly[display],
            )}
          >
            <ChevronDownIcon
              aria-hidden="true"
              className={cx(
                "size-4 transition-transform motion-reduce:transition-none",
                expanded && "rotate-180",
              )}
            />
          </button>
        )}
      </div>
      {hasChildren && (
        <ul
          id={childListId}
          hidden={!expanded}
          className={cx(
            "flex-col gap-1",
            display === "full" ? "flex" : fullOnly[display],
          )}
        >
          {item.children!.map((child) => (
            <NavigationItem
              key={child.id}
              item={child}
              depth={1}
              trail={trail}
              pathname={pathname}
              display={display}
              onNavigate={onNavigate}
            />
          ))}
        </ul>
      )}
    </li>
  );
}
