"use client";

import { Button } from "@/design-system/components/Button";
import { IconButton } from "@/design-system/components/IconButton";
import { Select } from "@/design-system/components/Select";
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  FirstPageIcon,
  LastPageIcon,
} from "@/design-system/icons";

// Pagination (DESIGN-SYSTEM.md §44, §74; T00-07C). Controlled and
// server-side ready: the caller owns `page` / `pageSize` and loads data in
// `onPageChange` / `onPageSizeChange`; the component never fetches.
// Tablet and up: summary, First / Previous, numbered pages with ellipses,
// Next / Last. Mobile: Previous · "Page x of y" · Next (44px targets).
// <nav> landmark; the current page has aria-current="page"; unavailable
// controls are disabled.

export type PaginationProps = {
  /** 1-based current page. */
  page: number;
  pageSize: number;
  totalItems: number;
  onPageChange: (page: number) => void;
  /** Rendered as a page-size Select when both are provided. */
  pageSizeOptions?: number[];
  onPageSizeChange?: (pageSize: number) => void;
  /** Accessible name of the navigation landmark. */
  label?: string;
  /** Plural noun for the summary, e.g. "records" (default "items"). */
  itemLabel?: string;
  locale?: string;
};

export type PageItem = number | "ellipsis-start" | "ellipsis-end";

/** Page numbers to show: first, last, current ±1, with ellipses for gaps. */
export function pageItems(page: number, totalPages: number): PageItem[] {
  if (totalPages <= 7)
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  const items: PageItem[] = [1];
  const start = Math.max(2, Math.min(page - 1, totalPages - 4));
  const end = Math.min(totalPages - 1, Math.max(page + 1, 5));
  if (start > 2) items.push("ellipsis-start");
  for (let p = start; p <= end; p += 1) items.push(p);
  if (end < totalPages - 1) items.push("ellipsis-end");
  items.push(totalPages);
  return items;
}

export function Pagination({
  page,
  pageSize,
  totalItems,
  onPageChange,
  pageSizeOptions,
  onPageSizeChange,
  label = "Pagination",
  itemLabel = "items",
  locale = "en-IN",
}: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
  const current = Math.min(Math.max(1, page), totalPages);
  const numberFormat = new Intl.NumberFormat(locale);
  const format = (value: number) => numberFormat.format(value);
  const first = totalItems === 0 ? 0 : (current - 1) * pageSize + 1;
  const last = Math.min(current * pageSize, totalItems);
  const isFirst = current <= 1;
  const isLast = current >= totalPages;
  const go = (target: number) =>
    onPageChange(Math.min(Math.max(1, target), totalPages));

  return (
    <nav
      aria-label={label}
      className="flex flex-col gap-3 tablet:flex-row tablet:items-center tablet:justify-between"
    >
      <p className="text-body-sm text-text-secondary">
        {totalItems === 0
          ? `No ${itemLabel}`
          : `Showing ${format(first)}–${format(last)} of ${format(totalItems)} ${itemLabel}`}
      </p>

      <div className="flex flex-wrap items-center gap-3">
        {pageSizeOptions && onPageSizeChange && (
          <div className="w-36">
            <Select
              label="Rows per page"
              options={pageSizeOptions.map((size) => ({
                id: String(size),
                label: String(size),
              }))}
              value={String(pageSize)}
              onChange={(id) => id && onPageSizeChange(Number(id))}
            />
          </div>
        )}

        {/* Mobile: compact */}
        <div className="flex w-full items-center justify-between gap-2 tablet:hidden">
          <IconButton
            label="Previous page"
            icon={ChevronLeftIcon}
            variant="secondary"
            isDisabled={isFirst}
            onPress={() => go(current - 1)}
          />
          <span className="text-body-sm font-medium text-text-primary">
            Page {format(current)} of {format(totalPages)}
          </span>
          <IconButton
            label="Next page"
            icon={ChevronRightIcon}
            variant="secondary"
            isDisabled={isLast}
            onPress={() => go(current + 1)}
          />
        </div>

        {/* Tablet and up: full */}
        <ul className="hidden items-center gap-1 tablet:flex">
          <li>
            <IconButton
              label="First page"
              icon={FirstPageIcon}
              isDisabled={isFirst}
              onPress={() => go(1)}
            />
          </li>
          <li>
            <IconButton
              label="Previous page"
              icon={ChevronLeftIcon}
              isDisabled={isFirst}
              onPress={() => go(current - 1)}
            />
          </li>
          {pageItems(current, totalPages).map((item) =>
            typeof item === "number" ? (
              <li key={item}>
                <Button
                  size="md"
                  variant={item === current ? "secondary" : "ghost"}
                  aria-current={item === current ? "page" : undefined}
                  aria-label={`Page ${item}`}
                  onPress={() => go(item)}
                >
                  {format(item)}
                </Button>
              </li>
            ) : (
              <li
                key={item}
                aria-hidden="true"
                className="px-1 text-body-sm text-text-muted"
              >
                …
              </li>
            ),
          )}
          <li>
            <IconButton
              label="Next page"
              icon={ChevronRightIcon}
              isDisabled={isLast}
              onPress={() => go(current + 1)}
            />
          </li>
          <li>
            <IconButton
              label="Last page"
              icon={LastPageIcon}
              isDisabled={isLast}
              onPress={() => go(totalPages)}
            />
          </li>
        </ul>
      </div>
    </nav>
  );
}
