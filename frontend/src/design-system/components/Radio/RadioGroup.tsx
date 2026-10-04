"use client";

import {
  Radio,
  RadioGroup as AriaRadioGroup,
  Text,
  type RadioGroupProps as AriaRadioGroupProps,
} from "react-aria-components";

import {
  FieldDescription,
  FieldErrorMessage,
  FieldLabel,
  type ErrorMessage,
} from "@/design-system/components/Field/Field";
import { cx, focusRing } from "@/design-system/lib/cx";

import type { ReactNode } from "react";

// RadioGroup (T00-07C; DESIGN-SYSTEM.md §42). React Aria: role=radiogroup
// labelled by its label, one Tab stop, arrow keys move and select, Space
// selects; required / invalid / disabled; `name` submits the value.
// Controlled (value + onChange) or uncontrolled (defaultValue). Vertical or
// horizontal (horizontal wraps). Selected = filled ring + inner dot + weight,
// not colour alone. Rows are 44px targets below the tablet breakpoint.

export type RadioOption = {
  value: string;
  label: string;
  description?: string;
  isDisabled?: boolean;
};

export type RadioGroupProps = Omit<
  AriaRadioGroupProps,
  "className" | "style" | "children"
> & {
  label: string;
  options: RadioOption[];
  description?: ReactNode;
  errorMessage?: ErrorMessage;
  /** Hide the label visually (keeps the accessible name; T01-09A choosers). */
  isLabelHidden?: boolean;
};

export function RadioGroup({
  label,
  options,
  description,
  errorMessage,
  orientation = "vertical",
  isLabelHidden = false,
  ...props
}: RadioGroupProps) {
  return (
    <AriaRadioGroup
      {...props}
      orientation={orientation}
      className="group flex flex-col gap-2"
    >
      <span className={cx(isLabelHidden && "sr-only")}>
        <FieldLabel isRequired={props.isRequired}>{label}</FieldLabel>
      </span>
      {description && <FieldDescription>{description}</FieldDescription>}
      <div
        className={cx(
          "flex gap-x-6 gap-y-1",
          orientation === "vertical" ? "flex-col" : "flex-row flex-wrap",
        )}
      >
        {options.map((option) => (
          <Radio
            key={option.value}
            value={option.value}
            isDisabled={option.isDisabled}
            className={cx(
              "group/radio flex min-h-control-lg w-fit cursor-pointer items-start gap-3 rounded-sm py-2 text-body-sm text-text-primary tablet:min-h-control-sm",
              "data-disabled:cursor-not-allowed data-disabled:opacity-50",
              focusRing,
            )}
          >
            {({ isSelected }) => (
              <>
                <span
                  aria-hidden="true"
                  className={cx(
                    "flex size-5 shrink-0 items-center justify-center rounded-full border-2 bg-surface-primary transition-colors motion-reduce:transition-none",
                    isSelected
                      ? "border-brand-primary"
                      : "border-border-strong group-data-hovered/radio:border-text-secondary",
                    "group-data-invalid/radio:border-error",
                  )}
                >
                  {isSelected && (
                    <span className="size-2 rounded-full bg-brand-primary" />
                  )}
                </span>
                <span className="flex flex-col">
                  <span className={cx(isSelected && "font-semibold")}>
                    {option.label}
                  </span>
                  {option.description && (
                    <Text
                      slot="description"
                      className="text-caption text-text-secondary"
                    >
                      {option.description}
                    </Text>
                  )}
                </span>
              </>
            )}
          </Radio>
        ))}
      </div>
      <FieldErrorMessage>{errorMessage}</FieldErrorMessage>
    </AriaRadioGroup>
  );
}
