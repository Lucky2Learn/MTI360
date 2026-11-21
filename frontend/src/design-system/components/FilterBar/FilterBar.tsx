"use client";

import { useState, type ReactNode } from "react";

import { Button } from "@/design-system/components/Button";
import { Drawer } from "@/design-system/components/Drawer";
import { FilterIcon } from "@/design-system/icons";
import { cx } from "@/design-system/lib/cx";

// FilterBar (DESIGN-SYSTEM.md §45, §85; T00-07C): layout composition for
// list screens — Search · filters (status, date, category, …) · Clear · Apply
// · result count. It owns no filter state and no business filters: callers
// pass controlled components (Search, Select, DatePicker, …) and handle
// onClear / onApply.
// One toolbar section (the Card surface): the search on the first row with
// Clear / Apply at its end, the filters below it in a balanced grid (two
// columns on tablet, three on desktop) — never a column of full-width selects
// beside an isolated search.
// - Mobile: the search with a compact "Filters (n)" button beside it; the
//   filters open in a bottom Drawer with Clear and Apply/Done (reuses Drawer).
// The result count is announced politely when it changes.

export type FilterBarProps = {
  /** Usually a <Search />. */
  search?: ReactNode;
  /** One-tap shortcuts (e.g. "My leads"): the first row of the toolbar on
   *  every width, never moved into the mobile drawer. */
  quickFilters?: ReactNode;
  /** Filter controls. Rendered inline from tablet, in a Drawer on mobile. */
  filters: ReactNode;
  /** Number of active filters shown on the mobile button and Clear action. */
  activeFilterCount?: number;
  /** Pre-formatted result summary, e.g. "128 results". */
  resultCount?: string;
  onClear?: () => void;
  /** When provided, filters are applied explicitly (Apply buttons). */
  onApply?: () => void;
  /** Accessible name of the filter group and drawer title. */
  label?: string;
};

export function FilterBar({
  search,
  quickFilters,
  filters,
  activeFilterCount = 0,
  resultCount,
  onClear,
  onApply,
  label = "Filters",
}: FilterBarProps) {
  const [isOpen, setOpen] = useState(false);
  const countSuffix = activeFilterCount > 0 ? ` (${activeFilterCount})` : "";

  return (
    <div className="flex min-w-0 flex-col gap-3">
      <div className="flex min-w-0 flex-col gap-4 rounded-xl border border-border-subtle bg-surface-primary p-3 tablet:p-4">
        {quickFilters}
        <div className="flex min-w-0 items-end gap-2 tablet:gap-3">
          {search && (
            <div className="min-w-0 flex-1 tablet:max-w-md">{search}</div>
          )}

          <div className={cx("shrink-0 tablet:hidden", !search && "flex-1")}>
            <Button
              variant="secondary"
              iconStart={FilterIcon}
              fullWidth={!search}
              aria-label={`${label}${countSuffix}`}
              onPress={() => setOpen(true)}
            >
              {/* Short visible text leaves room for the search beside it. */}
              {`Filters${countSuffix}`}
            </Button>
            <Drawer
              side="bottom"
              title={label}
              isOpen={isOpen}
              onOpenChange={setOpen}
              closeLabel={`Close ${label.toLowerCase()}`}
              actions={(close) => (
                <>
                  {onClear && (
                    <Button
                      variant="secondary"
                      isDisabled={activeFilterCount === 0}
                      onPress={onClear}
                    >
                      Clear filters
                    </Button>
                  )}
                  <Button
                    onPress={() => {
                      onApply?.();
                      close();
                    }}
                  >
                    {onApply ? "Apply" : "Done"}
                  </Button>
                </>
              )}
            >
              <div className="flex flex-col gap-4">{filters}</div>
            </Drawer>
          </div>

          {((onClear && activeFilterCount > 0) || onApply) && (
            <div className="ml-auto hidden shrink-0 items-center gap-2 tablet:flex">
              {onClear && activeFilterCount > 0 && (
                <Button variant="ghost" onPress={onClear}>
                  Clear filters
                </Button>
              )}
              {onApply && <Button onPress={onApply}>Apply</Button>}
            </div>
          )}
        </div>

        <div
          role="group"
          aria-label={label}
          className="hidden items-end gap-3 tablet:grid tablet:grid-cols-2 desktop:grid-cols-3"
        >
          {filters}
        </div>
      </div>

      {resultCount && (
        <p aria-live="polite" className="text-body-sm text-text-secondary">
          {resultCount}
        </p>
      )}
    </div>
  );
}
