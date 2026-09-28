import type { IconComponent } from "@/design-system/icons";

// Navigation model for the application shell (T00-08). Every experience
// supplies its own navigation as configuration (experiences/*.ts); the shell
// never assumes that experiences share a navigation. Visibility by role,
// permission, subscription or feature entitlement is NOT decided here: later
// phases filter this configuration server-side before it reaches the shell,
// and every route still enforces authorization on the server (CLAUDE.md §10, §62).

export type NavBadge = {
  /** Number shown in the navigation, e.g. 12. */
  count: number;
  /** Screen-reader description of the count, e.g. "12 unread". */
  label: string;
};

export type NavItem = {
  /** Stable identifier (unique within an experience). */
  id: string;
  label: string;
  /** Absolute application path, e.g. "/app/admissions/leads". */
  href: string;
  /** Decorative icon; required for top-level items of rail navigation. */
  icon?: IconComponent;
  badge?: NavBadge;
  /** Nested pages, shown under a disclosure. One level is supported. */
  children?: NavItem[];
};

export type NavSection = {
  id: string;
  /** Visible section heading; omit for an unlabelled first section. */
  label?: string;
  items: NavItem[];
};

export type Navigation = NavSection[];

/** Removes a trailing slash (except for the root) so "/app/" matches "/app". */
export function normalizePath(pathname: string): string {
  return pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
}

function isWithin(href: string, pathname: string): boolean {
  const base = normalizePath(href);
  const path = normalizePath(pathname);
  return path === base || path.startsWith(`${base}/`);
}

/**
 * The chain of navigation items that leads to `pathname`: the deepest item
 * whose href equals or contains the path, with its ancestors. Returns [] when
 * no item matches. Deeper and longer matches win, so a module page is not
 * attributed to the experience home ("/app" contains every tenant path).
 */
export function findTrail(navigation: Navigation, pathname: string): NavItem[] {
  let best: NavItem[] = [];
  const visit = (items: NavItem[], ancestors: NavItem[]) => {
    for (const item of items) {
      const trail = [...ancestors, item];
      if (isWithin(item.href, pathname)) {
        const current = best.at(-1);
        if (
          !current ||
          normalizePath(item.href).length > normalizePath(current.href).length
        ) {
          best = trail;
        }
      }
      if (item.children) visit(item.children, trail);
    }
  };
  for (const section of navigation) visit(section.items, []);
  return best;
}

/** True when `pathname` is exactly the page of `item`. */
export function isCurrentPage(item: NavItem, pathname: string): boolean {
  return normalizePath(item.href) === normalizePath(pathname);
}

/** Every item (including nested items) in navigation order. */
export function flattenNavigation(navigation: Navigation): NavItem[] {
  const items: NavItem[] = [];
  const visit = (list: NavItem[]) => {
    for (const item of list) {
      items.push(item);
      if (item.children) visit(item.children);
    }
  };
  for (const section of navigation) visit(section.items);
  return items;
}
