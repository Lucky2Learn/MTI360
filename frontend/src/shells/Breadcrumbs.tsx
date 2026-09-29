import Link from "next/link";

import { ChevronRightIcon } from "@/design-system/icons";
import { cx, focusRing } from "@/design-system/lib/cx";

// Breadcrumbs (T00-08; WAI-ARIA breadcrumb pattern): <nav aria-label> with an
// ordered list of links; the last item is the current page (aria-current).
// Separators are decorative. On mobile the middle items collapse to an
// ellipsis (first, parent and current remain), and long labels truncate, so
// the trail never causes horizontal overflow. Full trail from tablet up.

export type BreadcrumbItem = {
  label: string;
  /** Omit for the current page (the last item). */
  href?: string;
};

export type BreadcrumbsProps = {
  items: BreadcrumbItem[];
  /** Accessible name of the landmark. */
  label?: string;
};

export function Breadcrumbs({ items, label = "Breadcrumb" }: BreadcrumbsProps) {
  if (items.length === 0) return null;
  const lastIndex = items.length - 1;
  // Items between the first and the parent of the current page.
  const isCollapsible = (index: number) => index > 0 && index < lastIndex - 1;
  const hasCollapsed = items.some((_, index) => isCollapsible(index));

  return (
    <nav aria-label={label}>
      <ol className="flex min-w-0 items-center gap-1 text-body-sm">
        {items.map((item, index) => {
          const isCurrent = index === lastIndex;
          return [
            index === 1 && hasCollapsed && (
              <li
                key="collapsed"
                aria-hidden="true"
                className="flex shrink-0 items-center gap-1 text-text-muted tablet:hidden"
              >
                <ChevronRightIcon className="size-4 shrink-0" />…
              </li>
            ),
            <li
              key={`${index}-${item.label}`}
              className={cx(
                "flex min-w-0 items-center gap-1",
                isCollapsible(index) && "hidden tablet:flex",
                isCurrent && "shrink",
                !isCurrent && "shrink-0",
              )}
            >
              {index > 0 && (
                <ChevronRightIcon
                  aria-hidden="true"
                  className="size-4 shrink-0 text-text-muted"
                />
              )}
              {isCurrent ? (
                <span
                  aria-current="page"
                  className="truncate font-medium text-text-primary"
                >
                  {item.label}
                </span>
              ) : item.href ? (
                <Link
                  href={item.href}
                  className={cx(
                    // 44px touch target on mobile, compact from tablet (T00-10).
                    "inline-flex min-h-11 max-w-40 items-center truncate rounded-xs text-link underline-offset-4 hover:underline tablet:min-h-6 tablet:max-w-60",
                    focusRing,
                  )}
                >
                  <span className="truncate">{item.label}</span>
                </Link>
              ) : (
                <span className="max-w-40 truncate text-text-secondary tablet:max-w-60">
                  {item.label}
                </span>
              )}
            </li>,
          ];
        })}
      </ol>
    </nav>
  );
}
