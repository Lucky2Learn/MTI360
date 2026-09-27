"use client";

import {
  ListBox,
  ListBoxItem,
  Popover,
  Text,
  type ListBoxProps,
} from "react-aria-components";

import { CheckIcon } from "@/design-system/icons";
import { cx } from "@/design-system/lib/cx";

import type { ReactNode } from "react";

// Shared option list for Select and Combobox (internal, T00-07B).
// The popover is portalled to <body> by React Aria and follows the theme via
// the semantic tokens on <html>. It matches the trigger width, stays within
// the viewport (React Aria flips/shifts) and scrolls. Options are 44px tall
// below the tablet breakpoint. Selection = check mark + selected surface +
// weight, never colour alone.

export type Option = {
  /** Stable id submitted with the form (string). */
  id: string;
  label: string;
  description?: string;
  isDisabled?: boolean;
};

export function FieldPopover({ children }: { children: ReactNode }) {
  return (
    <Popover
      placement="bottom start"
      offset={4}
      className="z-(--z-dropdown) max-h-72 w-(--trigger-width) overflow-auto rounded-md border border-border-default bg-surface-elevated p-1 text-text-primary shadow-lg outline-none"
    >
      {children}
    </Popover>
  );
}

export function OptionList({
  emptyState,
  ...props
}: Omit<
  ListBoxProps<Option>,
  "className" | "style" | "children" | "renderEmptyState"
> & {
  emptyState?: ReactNode;
}) {
  return (
    <ListBox<Option>
      {...props}
      renderEmptyState={() => (
        <p className="px-3 py-2 text-body-sm text-text-muted">{emptyState}</p>
      )}
      className="flex flex-col gap-1 outline-none"
    >
      {(option) => (
        <ListBoxItem
          id={option.id}
          textValue={option.label}
          isDisabled={option.isDisabled}
          className={cx(
            "flex min-h-control-lg cursor-pointer items-center gap-2 rounded-sm px-3 py-2 text-body-sm text-text-primary outline-none tablet:min-h-control-md",
            "data-focused:bg-surface-hover data-selected:bg-surface-selected data-selected:font-semibold",
            "data-focus-visible:outline-solid data-focus-visible:outline-(length:--focus-ring-width) data-focus-visible:-outline-offset-2 data-focus-visible:outline-focus-ring",
            "data-disabled:cursor-not-allowed data-disabled:opacity-50",
          )}
        >
          {({ isSelected }) => (
            <>
              <span
                aria-hidden="true"
                className="flex size-4 shrink-0 items-center"
              >
                {isSelected && <CheckIcon className="size-4" />}
              </span>
              <span className="flex min-w-0 flex-col">
                <Text slot="label" className="truncate">
                  {option.label}
                </Text>
                {option.description && (
                  <Text
                    slot="description"
                    className="text-caption font-normal text-text-secondary"
                  >
                    {option.description}
                  </Text>
                )}
              </span>
            </>
          )}
        </ListBoxItem>
      )}
    </ListBox>
  );
}
