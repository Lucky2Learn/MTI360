"use client";

import { useId, type ReactNode } from "react";
import {
  Button as AriaButton,
  ComboBox as AriaComboBox,
  Input as AriaInput,
  type ComboBoxProps as AriaComboBoxProps,
} from "react-aria-components";

import {
  FieldDescription,
  FieldErrorMessage,
  FieldLabel,
  FieldSuccessMessage,
  fieldFocus,
  fieldStack,
  fieldSurface,
  type ErrorMessage,
} from "@/design-system/components/Field/Field";
import {
  FieldPopover,
  OptionList,
  type Option,
} from "@/design-system/components/Field/Listbox";
import { ChevronDownIcon, SpinnerIcon } from "@/design-system/icons";
import { cx } from "@/design-system/lib/cx";

// Combobox (DESIGN-SYSTEM.md §42, §69): type to filter a longer list.
// - filtering="contains" (default): the component filters `options` itself.
// - filtering="manual": async-ready — the caller owns `inputValue` /
//   `onInputChange`, supplies already-filtered `options` and sets `isLoading`.
//   The component never fetches anything.
// React Aria: role=combobox with aria-expanded/aria-activedescendant; arrows
// move, Enter selects, Escape closes/clears. Custom values are off by default
// (the input reverts to the selected option on blur). `name` submits the
// selected option id. An empty list shows a message in the listbox; loading is
// announced through a polite status region and shown by a spinner.

export type ComboboxProps = Omit<
  AriaComboBoxProps<Option>,
  | "className"
  | "style"
  | "children"
  | "items"
  | "defaultItems"
  | "value"
  | "defaultValue"
  | "onChange"
  | "selectedKey"
  | "defaultSelectedKey"
  | "onSelectionChange"
  | "allowsEmptyCollection"
> & {
  label: string;
  options: Option[];
  value?: string | null;
  defaultValue?: string | null;
  onChange?: (id: string | null) => void;
  filtering?: "contains" | "manual";
  isLoading?: boolean;
  placeholder?: string;
  emptyMessage?: string;
  loadingMessage?: string;
  description?: ReactNode;
  errorMessage?: ErrorMessage;
  successMessage?: string;
};

export function Combobox({
  label,
  options,
  value,
  defaultValue,
  onChange,
  filtering = "contains",
  isLoading = false,
  placeholder,
  emptyMessage = "No matches",
  loadingMessage = "Loading options…",
  description,
  errorMessage,
  successMessage,
  ...props
}: ComboboxProps) {
  const successId = useId();
  const collection =
    filtering === "manual" ? { items: options } : { defaultItems: options };

  return (
    <AriaComboBox
      {...props}
      {...collection}
      selectedKey={value}
      defaultSelectedKey={defaultValue}
      onSelectionChange={(key) => onChange?.(key === null ? null : String(key))}
      allowsEmptyCollection
      aria-describedby={
        cx(props["aria-describedby"], successMessage && successId) || undefined
      }
      className={cx(fieldStack, "group")}
    >
      <FieldLabel isRequired={props.isRequired}>{label}</FieldLabel>
      <div className="relative">
        <AriaInput
          placeholder={placeholder}
          className={cx(
            fieldSurface,
            fieldFocus,
            "h-control-md pr-12 pl-3 placeholder:text-text-muted",
          )}
        />
        <span className="absolute inset-y-0 right-1 flex items-center gap-1">
          {isLoading && (
            <SpinnerIcon
              aria-hidden="true"
              className="size-4 text-text-muted motion-safe:animate-spin"
            />
          )}
          <AriaButton className="flex size-control-sm cursor-pointer items-center justify-center rounded-sm text-text-secondary outline-none data-hovered:bg-surface-hover data-focus-visible:outline-solid data-focus-visible:outline-(length:--focus-ring-width) data-focus-visible:outline-focus-ring">
            <ChevronDownIcon
              aria-hidden="true"
              className="size-4 transition-transform group-data-open:rotate-180 motion-reduce:transition-none"
            />
          </AriaButton>
        </span>
      </div>
      {description && <FieldDescription>{description}</FieldDescription>}
      <FieldErrorMessage>{errorMessage}</FieldErrorMessage>
      {successMessage && (
        <FieldSuccessMessage id={successId}>
          {successMessage}
        </FieldSuccessMessage>
      )}
      <FieldPopover>
        {/* Inside the popover: React Aria hides content outside an open popover
            from assistive technology. ListBox does not forward aria-busy. */}
        <span role="status" className="sr-only">
          {isLoading ? loadingMessage : ""}
        </span>
        <OptionList emptyState={isLoading ? loadingMessage : emptyMessage} />
      </FieldPopover>
    </AriaComboBox>
  );
}
