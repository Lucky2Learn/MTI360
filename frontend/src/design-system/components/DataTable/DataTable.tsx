"use client";

import { useId, type ReactNode } from "react";
import { Button as AriaButton } from "react-aria-components";

import { Checkbox } from "@/design-system/components/Checkbox";
import { EmptyState } from "@/design-system/components/EmptyState";
import { ErrorState } from "@/design-system/components/ErrorState";
import { Skeleton } from "@/design-system/components/Skeleton";
import {
  SortAscendingIcon,
  SortDescendingIcon,
  SortableIcon,
} from "@/design-system/icons";
import { cx, focusRing } from "@/design-system/lib/cx";

// DataTable (DESIGN-SYSTEM.md §44, §27, §74; T00-07C). A typed, controlled
// foundation — never fetches; the application owns data, sorting, selection
// and paging (server-side ready, CLAUDE.md §52).
// - Semantic <table> with a caption; interactive parts are React Aria-based
//   components (sort buttons, the shared Checkbox, row-action buttons/menus),
//   so screen readers keep native table navigation.
// - Sorting: sortable headers cycle ascending → descending → unsorted;
//   aria-sort on the header, icon + state, never colour alone.
// - Selection (optional): "multiple" adds a select-all checkbox with an
//   indeterminate state; "single" keeps at most one row selected.
// - States: loading (skeleton rows, aria-busy, polite status), error
//   (ErrorState + retry), empty (EmptyState). Messages come from the caller.
// - Responsive: "scroll" keeps the table and scrolls horizontally inside a
//   focusable region (the page never overflows); columns can be hidden below
//   tablet/desktop. "cards" renders each row as a card below tablet.

export type SortDirection = "ascending" | "descending";
export type SortDescriptor = { columnId: string; direction: SortDirection };

export type DataTableColumn<Row> = {
  id: string;
  header: string;
  cell: (row: Row) => ReactNode;
  isSortable?: boolean;
  align?: "start" | "end";
  /** Marks the column that names the row (rendered as a row header). */
  isRowHeader?: boolean;
  /** Hide in table layout below this breakpoint. */
  visibleFrom?: "tablet" | "desktop";
};

export type DataTableEmptyState = {
  title: string;
  description: ReactNode;
  action?: ReactNode;
};
export type DataTableErrorState = {
  title: string;
  description?: ReactNode;
  onRetry?: () => void;
  reference?: string;
};

export type DataTableProps<Row> = {
  /** Accessible name (table caption, visually hidden). */
  label: string;
  columns: DataTableColumn<Row>[];
  rows: Row[];
  getRowId: (row: Row) => string;
  /** Used in selection-checkbox labels, e.g. "Select Arjun Menon". Default: id. */
  getRowLabel?: (row: Row) => string;
  sort?: SortDescriptor | null;
  onSortChange?: (sort: SortDescriptor | null) => void;
  selectionMode?: "none" | "single" | "multiple";
  selectedIds?: ReadonlySet<string>;
  onSelectionChange?: (ids: Set<string>) => void;
  /** Row-action area (buttons, DropdownMenu). */
  rowActions?: (row: Row) => ReactNode;
  rowActionsLabel?: string;
  isLoading?: boolean;
  loadingLabel?: string;
  loadingRows?: number;
  error?: DataTableErrorState | null;
  emptyState?: DataTableEmptyState;
  /** Rendered below the table, e.g. <Pagination />. */
  footer?: ReactNode;
  mobileLayout?: "scroll" | "cards";
};

const visibility: Record<"tablet" | "desktop", string> = {
  tablet: "hidden tablet:table-cell",
  desktop: "hidden desktop:table-cell",
};

function nextSort(
  current: SortDescriptor | null | undefined,
  columnId: string,
): SortDescriptor | null {
  if (current?.columnId !== columnId)
    return { columnId, direction: "ascending" };
  if (current.direction === "ascending")
    return { columnId, direction: "descending" };
  return null;
}

export function DataTable<Row>({
  label,
  columns,
  rows,
  getRowId,
  getRowLabel = getRowId,
  sort,
  onSortChange,
  selectionMode = "none",
  selectedIds = new Set<string>(),
  onSelectionChange,
  rowActions,
  rowActionsLabel = "Actions",
  isLoading = false,
  loadingLabel = "Loading",
  loadingRows = 5,
  error,
  emptyState = {
    title: "No results",
    description: "There is nothing to show here yet.",
  },
  footer,
  mobileLayout = "scroll",
}: DataTableProps<Row>) {
  const captionId = useId();
  const selectable = selectionMode !== "none";
  const ids = rows.map(getRowId);
  const selectedOnPage = ids.filter((id) => selectedIds.has(id)).length;
  const allSelected = ids.length > 0 && selectedOnPage === ids.length;
  const someSelected = selectedOnPage > 0 && !allSelected;
  const columnCount =
    columns.length + (selectable ? 1 : 0) + (rowActions ? 1 : 0);
  const showRows = !isLoading && !error && rows.length > 0;

  const toggleRow = (id: string, isSelected: boolean) => {
    if (selectionMode === "single") {
      onSelectionChange?.(new Set(isSelected ? [id] : []));
      return;
    }
    const next = new Set(selectedIds);
    if (isSelected) next.add(id);
    else next.delete(id);
    onSelectionChange?.(next);
  };

  const toggleAll = (isSelected: boolean) => {
    const next = new Set(selectedIds);
    for (const id of ids) {
      if (isSelected) next.add(id);
      else next.delete(id);
    }
    onSelectionChange?.(next);
  };

  const selectionCheckbox = (row: Row) => {
    const id = getRowId(row);
    return (
      <Checkbox
        isSelected={selectedIds.has(id)}
        onChange={(isSelected) => toggleRow(id, isSelected)}
      >
        <span className="sr-only">Select {getRowLabel(row)}</span>
      </Checkbox>
    );
  };

  const stateCell = (content: ReactNode) => (
    <tr>
      <td colSpan={columnCount} className="px-4">
        {content}
      </td>
    </tr>
  );

  const stateContent = error ? (
    <ErrorState
      titleAs="h3"
      title={error.title}
      description={error.description}
      onRetry={error.onRetry}
      reference={error.reference}
    />
  ) : (
    <EmptyState
      titleAs="h3"
      title={emptyState.title}
      description={emptyState.description}
      primaryAction={emptyState.action}
    />
  );

  const cards = mobileLayout === "cards";

  return (
    <div className="flex flex-col gap-4">
      <div className="overflow-hidden rounded-xl border border-border-subtle bg-surface-primary">
        {isLoading && (
          <p role="status" className="sr-only">
            {loadingLabel}
          </p>
        )}
        <div
          role="region"
          aria-labelledby={captionId}
          // A horizontally scrollable region must be keyboard-focusable so it
          // can be scrolled without a pointer (WCAG 2.1.1, axe
          // scrollable-region-focusable). Scoped to this element.
          // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
          tabIndex={0}
          className={cx(
            "overflow-x-auto",
            focusRing,
            cards && "hidden tablet:block",
          )}
        >
          <table
            aria-busy={isLoading || undefined}
            className="w-full min-w-full border-collapse text-body-sm"
          >
            <caption id={captionId} className="sr-only">
              {label}
            </caption>
            <thead className="bg-surface-secondary">
              <tr>
                {selectable && (
                  <th scope="col" className="w-12 px-4 py-2 text-left">
                    {selectionMode === "multiple" ? (
                      <Checkbox
                        isSelected={allSelected}
                        isIndeterminate={someSelected}
                        isDisabled={!showRows}
                        onChange={toggleAll}
                      >
                        <span className="sr-only">Select all rows</span>
                      </Checkbox>
                    ) : (
                      <span className="sr-only">Selection</span>
                    )}
                  </th>
                )}
                {columns.map((column) => {
                  const direction =
                    sort?.columnId === column.id ? sort.direction : undefined;
                  const SortIcon =
                    direction === "ascending"
                      ? SortAscendingIcon
                      : direction === "descending"
                        ? SortDescendingIcon
                        : SortableIcon;
                  return (
                    <th
                      key={column.id}
                      scope="col"
                      aria-sort={
                        column.isSortable ? (direction ?? "none") : undefined
                      }
                      className={cx(
                        "px-4 py-3 text-caption font-semibold whitespace-nowrap text-text-secondary",
                        column.align === "end" ? "text-right" : "text-left",
                        column.visibleFrom && visibility[column.visibleFrom],
                      )}
                    >
                      {column.isSortable && onSortChange ? (
                        <AriaButton
                          onPress={() =>
                            onSortChange(nextSort(sort, column.id))
                          }
                          className={cx(
                            "-mx-2 inline-flex min-h-control-sm cursor-pointer items-center gap-1 rounded-sm px-2 font-semibold data-hovered:text-text-primary",
                            direction && "text-text-primary",
                            focusRing,
                          )}
                        >
                          {column.header}
                          <SortIcon
                            aria-hidden="true"
                            className={cx(
                              "size-4",
                              !direction && "text-text-muted",
                            )}
                          />
                        </AriaButton>
                      ) : (
                        column.header
                      )}
                    </th>
                  );
                })}
                {rowActions && (
                  <th
                    scope="col"
                    className="px-4 py-3 text-right text-caption font-semibold text-text-secondary"
                  >
                    {rowActionsLabel}
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {isLoading &&
                Array.from({ length: loadingRows }, (_, index) => (
                  <tr
                    key={index}
                    aria-hidden="true"
                    className="border-t border-border-subtle"
                  >
                    {Array.from({ length: columnCount }, (_, cell) => (
                      <td key={cell} className="px-4 py-3">
                        <Skeleton width={cell === 0 ? "3/4" : "1/2"} />
                      </td>
                    ))}
                  </tr>
                ))}
              {!isLoading &&
                (error || rows.length === 0) &&
                stateCell(stateContent)}
              {showRows &&
                rows.map((row) => {
                  const id = getRowId(row);
                  const isSelected = selectedIds.has(id);
                  return (
                    <tr
                      key={id}
                      className={cx(
                        "border-t border-border-subtle transition-colors motion-reduce:transition-none",
                        isSelected
                          ? "bg-surface-selected"
                          : "hover:bg-surface-hover",
                      )}
                    >
                      {selectable && (
                        <td className="px-4 py-2">{selectionCheckbox(row)}</td>
                      )}
                      {columns.map((column) => {
                        const Cell = column.isRowHeader ? "th" : "td";
                        return (
                          <Cell
                            key={column.id}
                            {...(column.isRowHeader ? { scope: "row" } : {})}
                            className={cx(
                              "px-4 py-3 align-middle text-text-primary",
                              column.isRowHeader && "font-semibold",
                              column.align === "end"
                                ? "text-right tabular-nums"
                                : "text-left",
                              column.visibleFrom &&
                                visibility[column.visibleFrom],
                            )}
                          >
                            {column.cell(row)}
                          </Cell>
                        );
                      })}
                      {rowActions && (
                        <td className="px-4 py-2 text-right">
                          <div className="inline-flex items-center justify-end gap-1">
                            {rowActions(row)}
                          </div>
                        </td>
                      )}
                    </tr>
                  );
                })}
            </tbody>
          </table>
        </div>

        {cards && (
          <div className="tablet:hidden">
            {isLoading && (
              <div aria-hidden="true" className="flex flex-col gap-3 p-4">
                {Array.from(
                  { length: Math.min(loadingRows, 3) },
                  (_, index) => (
                    <Skeleton key={index} height="block" />
                  ),
                )}
              </div>
            )}
            {!isLoading && (error || rows.length === 0) && (
              <div className="px-4">{stateContent}</div>
            )}
            {showRows && (
              <ul
                aria-label={label}
                className="flex flex-col divide-y divide-border-subtle"
              >
                {rows.map((row) => {
                  const id = getRowId(row);
                  const header =
                    columns.find((column) => column.isRowHeader) ?? columns[0];
                  return (
                    <li
                      key={id}
                      className={cx(
                        "flex flex-col gap-3 p-4",
                        selectedIds.has(id) && "bg-surface-selected",
                      )}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex min-w-0 items-start gap-2">
                          {selectable && selectionCheckbox(row)}
                          <p className="pt-2 text-body-sm font-semibold text-text-primary">
                            {header?.cell(row)}
                          </p>
                        </div>
                        {rowActions && (
                          <div className="flex shrink-0 gap-1">
                            {rowActions(row)}
                          </div>
                        )}
                      </div>
                      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-body-sm">
                        {columns
                          .filter((column) => column !== header)
                          .map((column) => (
                            <div
                              key={column.id}
                              className="flex min-w-0 flex-col"
                            >
                              <dt className="text-caption text-text-muted">
                                {column.header}
                              </dt>
                              <dd className="text-text-primary">
                                {column.cell(row)}
                              </dd>
                            </div>
                          ))}
                      </dl>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        )}
      </div>
      {footer}
    </div>
  );
}
