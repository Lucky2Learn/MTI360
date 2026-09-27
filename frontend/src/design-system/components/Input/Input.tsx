"use client";

import { useId, type ReactNode } from "react";
import {
  Input as AriaInput,
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
import type { IconComponent } from "@/design-system/icons";
import { cx } from "@/design-system/lib/cx";

// Input (DESIGN-SYSTEM.md §42): single-line text entry on React Aria
// TextField. Controlled (value + onChange) or uncontrolled (defaultValue);
// `name` submits with the form. Validation: isRequired, type (email/url),
// minLength/maxLength/pattern, `validate`, isInvalid + errorMessage, and
// server errors through <Form validationErrors>. States: default, hover,
// focus, filled, disabled, read-only, error, success (opt-in).

export type InputType =
  "text" | "email" | "tel" | "url" | "password" | "search";

export type InputProps = Omit<
  TextFieldProps,
  "className" | "style" | "children" | "type"
> & {
  label: string;
  type?: InputType;
  placeholder?: string;
  description?: ReactNode;
  errorMessage?: ErrorMessage;
  /** Opt-in confirmation, e.g. "Email verified." (never automatic). */
  successMessage?: string;
  /** Decorative leading icon. */
  icon?: IconComponent;
};

export function Input({
  label,
  type = "text",
  placeholder,
  description,
  errorMessage,
  successMessage,
  icon: Icon,
  ...props
}: InputProps) {
  const successId = useId();
  return (
    <TextField
      {...props}
      type={type}
      aria-describedby={
        cx(props["aria-describedby"], successMessage && successId) || undefined
      }
      className={cx(fieldStack, "group")}
    >
      <FieldLabel isRequired={props.isRequired}>{label}</FieldLabel>
      <div className="relative">
        {Icon && (
          <Icon
            aria-hidden="true"
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-text-muted"
          />
        )}
        <AriaInput
          placeholder={placeholder}
          className={cx(
            fieldSurface,
            fieldFocus,
            "h-control-md px-3 placeholder:text-text-muted",
            "group-data-readonly:bg-surface-secondary",
            Icon && "pl-10",
          )}
        />
      </div>
      {description && <FieldDescription>{description}</FieldDescription>}
      <FieldErrorMessage>{errorMessage}</FieldErrorMessage>
      {successMessage && (
        <FieldSuccessMessage id={successId}>
          {successMessage}
        </FieldSuccessMessage>
      )}
    </TextField>
  );
}
