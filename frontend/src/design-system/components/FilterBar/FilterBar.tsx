"use client";

import { useState, type ReactNode } from "react";

import { Button } from "@/design-system/components/Button";
import { Drawer } from "@/design-system/components/Drawer";
import { FilterIcon } from "@/design-system/icons";

// FilterBar (DESIGN-SYSTEM.md §45, §85; T00-07C): layout composition for
// list screens — Search · filters (status, date, category, …) · Clear · Apply
// · result count. It owns no filter state and no business filters: callers
// pass controlled components (Search, Select, DatePicker, …) and handle
// onClear / onApply.
// - Tablet and up: search and filters inline (wrapping), Clear/Apply at the end.
// - Mobile: the search stays inline; a "Filters (n)" button opens the filters
//   in a bottom Drawer with Clear and Apply/Done actions (reuses Drawer).
// The result count is announced politely when it changes.

export type FilterBarProps = {
  /** Usually a <Search />. */
  search?: ReactNode;
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
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-3 tablet:flex-row tablet:flex-wrap tablet:items-end">
        {search && <div className="w-full tablet:w-72">{search}</div>}

        <div
          role="group"
          aria-label={label}
          className="hidden flex-1 flex-wrap items-end gap-3 tablet:flex"
        >
          {filters}
          {onClear && activeFilterCount > 0 && (
            <Button variant="ghost" onPress={onClear}>
              Clear filters
            </Button>
          )}
          {onApply && <Button onPress={onApply}>Apply</Button>}
        </div>

        <div className="tablet:hidden">
          <Button
            variant="secondary"
            iconStart={FilterIcon}
            fullWidth
            onPress={() => setOpen(true)}
          >
            {`${label}${countSuffix}`}
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
      </div>

      {resultCount && (
        <p aria-live="polite" className="text-body-sm text-text-secondary">
          {resultCount}
        </p>
      )}
    </div>
  );
}
