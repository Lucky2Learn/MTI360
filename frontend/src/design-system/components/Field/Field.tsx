"use client";

import {
  FieldError,
  Form as AriaForm,
  Label,
  Text,
  type FormProps as AriaFormProps,
  type ValidationResult,
} from "react-aria-components";

import { ErrorIcon, SuccessIcon } from "@/design-system/icons";
import { cx } from "@/design-system/lib/cx";

import type { ReactNode } from "react";

// Field foundation (T00-07B; DESIGN-SYSTEM.md §42, CLAUDE.md §34). Shared
// building blocks for every form control:
// - FieldLabel: visible label + required indicator "*" (decision D4); the
//   control itself carries the programmatic required state.
// - FieldDescription: help text (React Aria description slot → aria-describedby).
// - FieldErrorMessage: React Aria FieldError — error icon + text, rendered only
//   while the field is invalid, linked via aria-describedby. Never colour alone.
// - FieldSuccessMessage: opt-in success icon + text (decision D6).
// - Form: React Aria Form with native validation (decision D5) and
//   validationErrors for server-side errors keyed by field name.

export type ErrorMessage = string | ((validation: ValidationResult) => string);

/** Shared control surface (inputs, textareas, select/combobox/date triggers). */
export const fieldSurface = cx(
  "w-full rounded-md border border-border-strong bg-surface-primary text-body-sm text-text-primary",
  "transition-colors motion-reduce:transition-none",
  "data-hovered:border-text-secondary",
  "data-invalid:border-error",
  "data-disabled:cursor-not-allowed data-disabled:bg-surface-secondary data-disabled:opacity-50",
);

/** Focus for text-entry controls: visible on every focus, not only keyboard. */
export const fieldFocus =
  "outline-none data-focused:border-focus-ring data-focused:outline-solid data-focused:outline-(length:--focus-ring-width) data-focused:outline-offset-0 data-focused:outline-focus-ring";

/** Same focus treatment for wrappers that contain the focused element. */
export const fieldFocusWithin =
  "outline-none data-focus-within:border-focus-ring data-focus-within:outline-solid data-focus-within:outline-(length:--focus-ring-width) data-focus-within:outline-offset-0 data-focus-within:outline-focus-ring";

export function FieldLabel({
  children,
  isRequired = false,
}: {
  children: ReactNode;
  isRequired?: boolean;
}) {
  return (
    <Label className="text-body-sm font-medium text-text-primary">
      {children}
      {isRequired && (
        <span aria-hidden="true" className="ml-1 text-error-text">
          *
        </span>
      )}
    </Label>
  );
}

export function FieldDescription({ children }: { children: ReactNode }) {
  return (
    <Text slot="description" className="text-caption text-text-secondary">
      {children}
    </Text>
  );
}

export function FieldErrorMessage({ children }: { children?: ErrorMessage }) {
  return (
    <FieldError className="flex items-start gap-1 text-caption font-medium text-error-text">
      {(validation) => (
        <>
          <ErrorIcon aria-hidden="true" className="size-4 shrink-0" />
          <span>
            {typeof children === "function"
              ? children(validation)
              : (children ?? validation.validationErrors.join(" "))}
          </span>
        </>
      )}
    </FieldError>
  );
}

export function FieldSuccessMessage({
  id,
  children,
}: {
  id: string;
  children: ReactNode;
}) {
  return (
    <p
      id={id}
      className="flex items-start gap-1 text-caption font-medium text-success-text"
    >
      <SuccessIcon aria-hidden="true" className="size-4 shrink-0" />
      <span>{children}</span>
    </p>
  );
}

/** Vertical stack for label, control and messages (4px grid). */
export const fieldStack = "flex w-full flex-col gap-2";

export type FormProps = Omit<AriaFormProps, "className" | "style"> & {
  children: ReactNode;
};

/**
 * Form with native validation by default: invalid submits are blocked, errors
 * appear after submit or commit, and the first invalid field receives focus.
 * `validationErrors` ({ fieldName: message }) shows server-side errors on the
 * matching fields until the user edits them.
 */
export function Form({
  children,
  validationBehavior = "native",
  ...props
}: FormProps) {
  return (
    <AriaForm
      {...props}
      validationBehavior={validationBehavior}
      className="flex flex-col gap-6"
    >
      {children}
    </AriaForm>
  );
}
