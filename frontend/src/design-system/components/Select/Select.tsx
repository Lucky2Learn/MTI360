"use client";

import { useId, type ReactNode } from "react";
import {
  Button as AriaButton,
  Select as AriaSelect,
  SelectValue,
  type SelectProps as AriaSelectProps,
} from "react-aria-components";

import {
  FieldDescription,
  FieldErrorMessage,
  FieldLabel,
  FieldSuccessMessage,
  fieldStack,
  type ErrorMessage,
} from "@/design-system/components/Field/Field";
import {
  FieldPopover,
  OptionList,
  type Option,
} from "@/design-system/components/Field/Listbox";
import { ChevronDownIcon } from "@/design-system/icons";
import { cx, focusRing } from "@/design-system/lib/cx";

// Select (DESIGN-SYSTEM.md §42): choose one option from a short, known list.
// React Aria: button with aria-haspopup=listbox; Enter/Space/ArrowDown open;
// arrows, Home/End and type-ahead move; Enter selects; Escape closes and
// returns focus. `name` renders a hidden native <select> for FormData.
// Popover on every screen size (decision D9).

export type SelectProps = Omit<
  AriaSelectProps<Option, "single">,
  | "className"
  | "style"
  | "children"
  | "items"
  | "value"
  | "defaultValue"
  | "onChange"
  | "selectedKey"
  | "defaultSelectedKey"
  | "onSelectionChange"
  | "selectionMode"
  | "placeholder"
> & {
  label: string;
  options: Option[];
  /** Selected option id (controlled); null = nothing selected. */
  value?: string | null;
  defaultValue?: string | null;
  onChange?: (id: string | null) => void;
  placeholder?: string;
  description?: ReactNode;
  errorMessage?: ErrorMessage;
  successMessage?: string;
};

export function Select({
  label,
  options,
  value,
  defaultValue,
  onChange,
  placeholder = "Select an option",
  description,
  errorMessage,
  successMessage,
  ...props
}: SelectProps) {
  const successId = useId();
  return (
    <AriaSelect
      {...props}
      selectedKey={value}
      defaultSelectedKey={defaultValue}
      onSelectionChange={(key) => onChange?.(key === null ? null : String(key))}
      placeholder={placeholder}
      aria-describedby={
        cx(props["aria-describedby"], successMessage && successId) || undefined
      }
      className={cx(fieldStack, "group")}
    >
      <FieldLabel isRequired={props.isRequired}>{label}</FieldLabel>
      <AriaButton
        className={cx(
          "flex h-control-md w-full cursor-pointer items-center justify-between gap-2 rounded-md border border-border-strong bg-surface-primary px-3 text-left text-body-sm text-text-primary",
          "transition-colors motion-reduce:transition-none",
          "data-hovered:border-text-secondary data-pressed:bg-surface-hover",
          "group-data-invalid:border-error",
          "data-disabled:cursor-not-allowed data-disabled:bg-surface-secondary data-disabled:opacity-50",
          focusRing,
        )}
      >
        <SelectValue className="truncate data-placeholder:text-text-muted" />
        <ChevronDownIcon
          aria-hidden="true"
          className="size-4 shrink-0 text-text-secondary transition-transform group-data-open:rotate-180 motion-reduce:transition-none"
        />
      </AriaButton>
      {description && <FieldDescription>{description}</FieldDescription>}
      <FieldErrorMessage>{errorMessage}</FieldErrorMessage>
      {successMessage && (
        <FieldSuccessMessage id={successId}>
          {successMessage}
        </FieldSuccessMessage>
      )}
      <FieldPopover>
        <OptionList items={options} emptyState="No options available" />
      </FieldPopover>
    </AriaSelect>
  );
}
