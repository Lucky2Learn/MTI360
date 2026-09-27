"use client";

import { useId, useState, type ReactNode } from "react";
import {
  TextArea as AriaTextArea,
  TextField,
  type TextFieldProps,
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
import { cx } from "@/design-system/lib/cx";

// Textarea (DESIGN-SYSTEM.md §42): multi-line text on React Aria TextField.
// Same validation and state model as Input. With maxLength + showCount a
// visible "n / max characters" count is linked as a description (read with
// the field, not announced on every keystroke). Resizes vertically only.

export type TextareaProps = Omit<
  TextFieldProps,
  "className" | "style" | "children" | "type"
> & {
  label: string;
  placeholder?: string;
  rows?: number;
  description?: ReactNode;
  errorMessage?: ErrorMessage;
  successMessage?: string;
  /** Show the character count (requires maxLength). */
  showCount?: boolean;
};

export function Textarea({
  label,
  placeholder,
  rows = 4,
  description,
  errorMessage,
  successMessage,
  showCount = false,
  onChange,
  ...props
}: TextareaProps) {
  const successId = useId();
  const countId = useId();
  const [uncontrolledLength, setUncontrolledLength] = useState(
    props.defaultValue?.length ?? 0,
  );
  const length =
    props.value !== undefined ? props.value.length : uncontrolledLength;
  const counted = showCount && props.maxLength !== undefined;

  return (
    <TextField
      {...props}
      onChange={(value) => {
        setUncontrolledLength(value.length);
        onChange?.(value);
      }}
      aria-describedby={
        cx(
          props["aria-describedby"],
          counted && countId,
          successMessage && successId,
        ) || undefined
      }
      className={cx(fieldStack, "group")}
    >
      <FieldLabel isRequired={props.isRequired}>{label}</FieldLabel>
      <AriaTextArea
        rows={rows}
        placeholder={placeholder}
        className={cx(
          fieldSurface,
          fieldFocus,
          "min-h-24 resize-y px-3 py-2 placeholder:text-text-muted",
          "group-data-readonly:bg-surface-secondary",
        )}
      />
      {(description || counted) && (
        <div className="flex items-start justify-between gap-3">
          {description ? (
            <FieldDescription>{description}</FieldDescription>
          ) : (
            <span />
          )}
          {counted && (
            <p
              id={countId}
              className="shrink-0 text-caption text-text-muted tabular-nums"
            >
              {length} / {props.maxLength} characters
            </p>
          )}
        </div>
      )}
      <FieldErrorMessage>{errorMessage}</FieldErrorMessage>
      {successMessage && (
        <FieldSuccessMessage id={successId}>
          {successMessage}
        </FieldSuccessMessage>
      )}
    </TextField>
  );
}
