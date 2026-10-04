"use client";

import { Alert, Button } from "@/design-system/components";
import { reloadDocument } from "@/lib/session/document";

import type { Feedback } from "./feedback";

// Shared pieces of the authentication screens (T01-09A).

/**
 * Form-level outcome (§10.1): one Alert at the top of the card body, inside
 * a container that is always mounted, so the inserted Alert is announced
 * (error: role="alert"; others: role="status").
 */
export function FeedbackRegion({ feedback }: { feedback: Feedback | null }) {
  return (
    <div data-slot="form-feedback" className="flex flex-col empty:hidden">
      {feedback && (
        <Alert
          tone={feedback.tone}
          title={feedback.title}
          action={
            feedback.reload ? (
              <Button variant="secondary" size="sm" onPress={reloadDocument}>
                Reload page
              </Button>
            ) : undefined
          }
        >
          {feedback.body}
        </Alert>
      )}
    </div>
  );
}

/** Static password rules (ADR-0010 §7), linked by aria-describedby. */
export function PasswordRequirements({ id }: { id: string }) {
  return (
    <ul
      id={id}
      className="flex list-disc flex-col gap-1 pl-5 text-body-sm text-text-secondary"
    >
      <li>Use 12 to 128 characters.</li>
      <li>Avoid common passwords. Spaces and any characters are allowed.</li>
      <li>You don&apos;t need special characters or numbers.</li>
    </ul>
  );
}

/** "* Required field" legend shown with every form (INC-23). */
export function RequiredLegend() {
  return (
    <p className="text-caption text-text-secondary">
      <span aria-hidden="true" className="text-error-text">
        *
      </span>{" "}
      Required field
    </p>
  );
}

export const PASSWORD_MIN_LENGTH = 12;
export const PASSWORD_MAX_LENGTH = 128;

/** Client length rule (UX only; the API validates authoritatively). */
export function passwordLengthError(value: string): string | null {
  if (value.length < PASSWORD_MIN_LENGTH) return "Use at least 12 characters.";
  if (value.length > PASSWORD_MAX_LENGTH) return "Use 128 characters or fewer.";
  return null;
}

type Validation = {
  validationDetails: ValidityState;
  validationErrors: string[];
};

/** New-password messages: an empty field gets the length rule (§8.3). */
export function newPasswordError(validation: Validation): string {
  return validation.validationDetails.valueMissing
    ? "Use at least 12 characters."
    : validation.validationErrors.join(" ");
}

/** Confirmation messages: an empty confirmation does not match. */
export function confirmPasswordError(validation: Validation): string {
  return validation.validationDetails.valueMissing
    ? "The passwords don't match."
    : validation.validationErrors.join(" ");
}

export const EMAIL_MAX_LENGTH = 254;

/** AUTH-01/02 email messages: missing vs. malformed. */
export function emailError(validation: {
  validationDetails: ValidityState;
}): string {
  return validation.validationDetails.valueMissing
    ? "Enter your email address."
    : "Enter an email address like name@institute.edu.";
}
