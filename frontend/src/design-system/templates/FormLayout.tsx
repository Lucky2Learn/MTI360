import { cx } from "@/design-system/lib/cx";

import type { ReactNode } from "react";

// Form layout — the T04 Form subset used by create/edit pages (Phase 02-1;
// DESIGN-SYSTEM.md §28, CLAUDE.md §34):
//
//   FormSection: a titled group (h2) of related fields with an optional hint;
//   FormGrid: one column on mobile, two from tablet (`span="full"` children
//     take the whole row, e.g. long text);
//   FormActions: primary action last; full-width stacked buttons on mobile,
//     sticky to the bottom of the viewport so Save is always reachable;
//     inline and end-aligned from tablet.

export function FormSection({
  title,
  description,
  children,
}: {
  title: string;
  description?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="flex min-w-0 flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h2 className="text-card-heading text-text-primary">{title}</h2>
        {description && (
          <p className="text-body-sm text-text-secondary">{description}</p>
        )}
      </div>
      {children}
    </section>
  );
}

export function FormGrid({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-w-0 grid-cols-1 gap-4 tablet:grid-cols-2 tablet:gap-x-6">
      {children}
    </div>
  );
}

/** A FormGrid cell; `span="full"` takes both columns from tablet. */
export function FormCell({
  span = "half",
  children,
}: {
  span?: "half" | "full";
  children: ReactNode;
}) {
  return (
    <div className={cx("min-w-0", span === "full" && "tablet:col-span-2")}>
      {children}
    </div>
  );
}

export function FormActions({ children }: { children: ReactNode }) {
  return (
    <div className="sticky bottom-0 z-(--z-sticky) -mx-4 flex flex-col-reverse gap-2 border-t border-border-subtle bg-background-primary px-4 py-3 tablet:static tablet:mx-0 tablet:flex-row tablet:justify-end tablet:border-0 tablet:bg-transparent tablet:px-0 tablet:py-0">
      {children}
    </div>
  );
}
