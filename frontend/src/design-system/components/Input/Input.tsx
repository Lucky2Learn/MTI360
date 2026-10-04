"use client";

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
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
import { IconButton } from "@/design-system/components/IconButton";
import { HideIcon, ViewIcon, type IconComponent } from "@/design-system/icons";
import { cx } from "@/design-system/lib/cx";

// Input (DESIGN-SYSTEM.md §42): single-line text entry on React Aria
// TextField. Controlled (value + onChange) or uncontrolled (defaultValue);
// `name` submits with the form. Validation: isRequired, type (email/url),
// minLength/maxLength/pattern, `validate`, isInvalid + errorMessage, and
// server errors through <Form validationErrors>. States: default, hover,
// focus, filled, disabled, read-only, error, success (opt-in).
//
// Revealable password (T01-09A; T01-04 UI contract §13, S15): with
// `type="password"` and `isRevealable`, an in-field toggle ("Show password" /
// "Hide password", aria-pressed, aria-controls = the input) switches the
// input between hidden and visible text. Focus stays on the toggle and the
// value is kept. The field is hidden again whenever its form is submitted.
// Paste is never blocked.

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
  /** Show/hide toggle; only with type="password". */
  isRevealable?: boolean;
  /** Virtual-keyboard capitalisation, e.g. "none" for emails and codes. */
  autoCapitalize?: "none" | "off" | "on" | "sentences" | "words" | "characters";
};

export function Input({
  label,
  type = "text",
  placeholder,
  description,
  errorMessage,
  successMessage,
  icon: Icon,
  isRevealable = false,
  autoCapitalize,
  ...props
}: InputProps) {
  const successId = useId();
  const generatedId = useId();
  const inputId = props.id ?? generatedId;
  const inputRef = useRef<HTMLInputElement>(null);
  const [revealed, setRevealed] = useState(false);
  const revealable = isRevealable && type === "password";

  // Hidden again after every submit of the enclosing form (S15).
  useEffect(() => {
    const form = inputRef.current?.form;
    if (!revealable || !form) return;
    const hide = () => setRevealed(false);
    form.addEventListener("submit", hide);
    return () => form.removeEventListener("submit", hide);
  }, [revealable]);

  return (
    <TextField
      {...props}
      id={inputId}
      type={revealable && revealed ? "text" : type}
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
          ref={inputRef}
          placeholder={placeholder}
          autoCapitalize={autoCapitalize}
          className={cx(
            fieldSurface,
            fieldFocus,
            "h-control-md px-3 placeholder:text-text-muted",
            "group-data-readonly:bg-surface-secondary",
            Icon && "pl-10",
            revealable && "pr-12",
          )}
        />
        {revealable && (
          <span className="absolute inset-y-0 right-0 flex items-center">
            <IconButton
              label={revealed ? "Hide password" : "Show password"}
              icon={revealed ? HideIcon : ViewIcon}
              aria-pressed={revealed}
              aria-controls={inputId}
              isDisabled={props.isDisabled}
              onPress={() => setRevealed((value) => !value)}
            />
          </span>
        )}
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
