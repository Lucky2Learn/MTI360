import Link from "next/link";

import { cx, focusRing } from "@/design-system/lib/cx";

import type { ReactNode } from "react";

// A link to a business record inside tables, cards and text (Phase 02-1).
// Underlined (never colour alone, WCAG 1.4.1) with the shared focus ring.
// `newTab` keeps the current page (e.g. a form in progress) and says so.

export function RecordLink({
  href,
  children,
  newTab = false,
}: {
  href: string;
  children: ReactNode;
  newTab?: boolean;
}) {
  return (
    <Link
      href={href}
      className={cx(
        "rounded-sm font-medium break-words text-link underline underline-offset-4",
        focusRing,
      )}
      {...(newTab ? { target: "_blank", rel: "noopener noreferrer" } : {})}
    >
      {children}
      {newTab && <span className="sr-only"> (opens in a new tab)</span>}
    </Link>
  );
}
