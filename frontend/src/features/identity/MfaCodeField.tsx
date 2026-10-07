"use client";

import { Input } from "@/design-system/components";

// MfaCodeField (T01-09B): the one input for authenticator and recovery codes,
// shared by the sign-in MFA step (tenant AUTH-04 verify, platform PLAT-02),
// platform enrolment (PAUTH-04) and step-up (PAUTH-07). The value is owned
// by the caller, which clears it after every attempt; it is never stored,
// logged or put in a URL. No auto-submit (WCAG 3.2.2).

export type MfaCodeKind = "totp" | "recovery";

export type MfaCodeFieldProps = {
  id?: string;
  kind?: MfaCodeKind;
  label: string;
  value: string;
  onChange: (value: string) => void;
  /** Server refusal (422): shows `invalidMessage`. */
  invalid?: boolean;
  invalidMessage: string;
  /** Shown when the field is submitted empty. */
  missingMessage: string;
  description?: string;
  autoFocus?: boolean;
};

export function MfaCodeField({
  id,
  kind = "totp",
  label,
  value,
  onChange,
  invalid = false,
  invalidMessage,
  missingMessage,
  description,
  autoFocus,
}: MfaCodeFieldProps) {
  const totp = kind === "totp";
  return (
    <Input
      id={id}
      label={label}
      name={totp ? "code" : "recovery_code"}
      isRequired
      // Focus moves here when a dialog opens (PAUTH-07); the page steps move
      // focus to their h1 instead.
      // eslint-disable-next-line jsx-a11y/no-autofocus
      autoFocus={autoFocus}
      autoComplete={totp ? "one-time-code" : "off"}
      inputMode={totp ? "numeric" : "text"}
      autoCapitalize="none"
      spellCheck="false"
      maxLength={totp ? 7 : 13}
      value={value}
      onChange={onChange}
      description={description}
      isInvalid={invalid || undefined}
      errorMessage={invalid ? invalidMessage : missingMessage}
    />
  );
}
