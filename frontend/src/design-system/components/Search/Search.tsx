"use client";

import { type ReactNode } from "react";
import {
  Button as AriaButton,
  Input as AriaInput,
  SearchField,
  type SearchFieldProps,
} from "react-aria-components";

import {
  FieldDescription,
  FieldLabel,
  fieldFocus,
  fieldStack,
  fieldSurface,
} from "@/design-system/components/Field/Field";
import { CloseIcon, SearchIcon, SpinnerIcon } from "@/design-system/icons";
import { cx, focusRing } from "@/design-system/lib/cx";

// Search (T00-07C; DESIGN-SYSTEM.md §87). React Aria SearchField: an
// <input type="search"> with a clear button; Escape clears, Enter submits.
// Controlled or uncontrolled. It never searches or debounces by itself —
// the application handles searching in onChange / onSubmit. The label may be
// visually hidden (it is always present for assistive technology).
// Optional `suggestions` slot renders below the field (e.g. recent searches);
// for an interactive suggestion list use Combobox.

export type SearchProps = Omit<
  SearchFieldProps,
  "className" | "style" | "children"
> & {
  label: string;
  /** Hide the label visually (keeps the accessible name). */
  isLabelHidden?: boolean;
  placeholder?: string;
  description?: ReactNode;
  isLoading?: boolean;
  loadingLabel?: string;
  suggestions?: ReactNode;
};

export function Search({
  label,
  isLabelHidden = false,
  placeholder = "Search",
  description,
  isLoading = false,
  loadingLabel = "Searching…",
  suggestions,
  ...props
}: SearchProps) {
  return (
    <SearchField {...props} className={cx(fieldStack, "group")}>
      <span className={cx(isLabelHidden && "sr-only")}>
        <FieldLabel>{label}</FieldLabel>
      </span>
      <div className="relative">
        <SearchIcon
          aria-hidden="true"
          className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-text-muted"
        />
        <AriaInput
          placeholder={placeholder}
          className={cx(
            fieldSurface,
            fieldFocus,
            "h-control-md pr-20 pl-10 placeholder:text-text-muted [&::-webkit-search-cancel-button]:hidden",
          )}
        />
        <span className="absolute inset-y-0 right-1 flex items-center gap-1">
          {isLoading && (
            <>
              <SpinnerIcon
                aria-hidden="true"
                className="size-4 text-text-muted motion-safe:animate-spin"
              />
              <span role="status" className="sr-only">
                {loadingLabel}
              </span>
            </>
          )}
          <AriaButton
            aria-label="Clear search"
            className={cx(
              "flex size-control-sm cursor-pointer items-center justify-center rounded-sm text-text-secondary data-hovered:bg-surface-hover group-data-empty:hidden",
              focusRing,
            )}
          >
            <CloseIcon aria-hidden="true" className="size-4" />
          </AriaButton>
        </span>
      </div>
      {description && <FieldDescription>{description}</FieldDescription>}
      {suggestions && <div className="text-body-sm">{suggestions}</div>}
    </SearchField>
  );
}
