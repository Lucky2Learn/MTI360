"use client";

import {
  CheckboxButton,
  CheckboxField,
  type CheckboxFieldProps,
} from "react-aria-components";

import {
  FieldDescription,
  FieldErrorMessage,
  type ErrorMessage,
} from "@/design-system/components/Field/Field";
import { CheckIcon, IndeterminateIcon } from "@/design-system/icons";
import { cx, focusRing } from "@/design-system/lib/cx";

import type { ReactNode } from "react";

// Checkbox (DESIGN-SYSTEM.md §42, §69) on React Aria CheckboxField +
// CheckboxButton (the React Aria 1.21 field API with description/error
// linkage). Controlled (isSelected + onChange) or uncontrolled
// (defaultSelected). isIndeterminate supports "select all" (DataTable, 07C) and
// is exposed as aria-checked="mixed". The whole label row is the target: 44px
// below the tablet breakpoint. State is shown by the check/minus mark, not
// colour alone.

export type CheckboxProps = Omit<
  CheckboxFieldProps,
  "className" | "style" | "children"
> & {
  /** Visible label (required). */
  children: ReactNode;
  description?: ReactNode;
  errorMessage?: ErrorMessage;
};

export function Checkbox({
  children,
  description,
  errorMessage,
  ...props
}: CheckboxProps) {
  return (
    <CheckboxField {...props} className="flex flex-col gap-1">
      <CheckboxButton
        className={cx(
          "group/check inline-flex min-h-control-lg w-fit cursor-pointer items-center gap-3 rounded-sm text-body-sm text-text-primary select-none tablet:min-h-control-sm",
          "data-disabled:cursor-not-allowed data-disabled:opacity-50",
          focusRing,
        )}
      >
        {({ isSelected, isIndeterminate }) => (
          <>
            <span
              aria-hidden="true"
              className={cx(
                "flex size-5 shrink-0 items-center justify-center rounded-xs border-2 border-border-strong bg-surface-primary text-text-inverse",
                "transition-colors motion-reduce:transition-none",
                "group-data-hovered/check:border-text-secondary",
                "group-data-selected/check:border-brand-primary group-data-selected/check:bg-brand-primary",
                "group-data-indeterminate/check:border-brand-primary group-data-indeterminate/check:bg-brand-primary",
                "group-data-invalid/check:border-error",
              )}
            >
              {isIndeterminate ? (
                <IndeterminateIcon className="size-4" strokeWidth={3} />
              ) : (
                isSelected && <CheckIcon className="size-4" strokeWidth={3} />
              )}
            </span>
            <span>{children}</span>
          </>
        )}
      </CheckboxButton>
      {description && (
        <div className="pl-8">
          <FieldDescription>{description}</FieldDescription>
        </div>
      )}
      <div className="pl-8">
        <FieldErrorMessage>{errorMessage}</FieldErrorMessage>
      </div>
    </CheckboxField>
  );
}
