"use client";

import { useId, useState, type FormEvent } from "react";

import { Button, Form, Input } from "@/design-system/components";
import { AuthenticationTemplate } from "@/design-system/templates/AuthenticationTemplate";
import { ApiError } from "@/lib/api/errors";
import type { SessionWire } from "@/lib/api/types";
import { authPost } from "@/lib/session/client";
import { assignLocation } from "@/lib/session/document";
import { destinationFor } from "@/lib/session/routes";

import { FeedbackRegion, RequiredLegend } from "./components";
import { commonFeedback, tooManyAttempts, type Feedback } from "./feedback";

// Tenant MFA step of sign-in (T01-09A scope: verify and recovery only;
// backend contract T01-06, POST /auth/mfa/verify and /auth/mfa/recovery).
// It follows a password sign-in that answered `mfa_required`: the pending
// session cookie is HttpOnly, and its CSRF token (from that response) is held
// in memory only. Codes live only in this component's state — cleared after
// every attempt, never stored or logged. No trusted device, "remember
// device", resend, passkeys, SMS or email codes (deferred, D6-4).
//
// Outcomes: success → the session's next step (full document navigation);
// wrong code (422) → field error; the pending session ended (401: expired
// after 5 minutes or too many wrong codes) → back to sign-in with a notice.

export const MFA_ENDED: Feedback = {
  tone: "warning",
  title: "Sign in again",
  body: "For your security, the verification step has ended. Sign in again to continue.",
};

type Mode = "totp" | "recovery";

const COPY: Record<
  Mode,
  {
    title: string;
    description: string;
    label: string;
    field: "code" | "recovery_code";
    path: "/mfa/verify" | "/mfa/recovery";
    missing: string;
    invalid: string;
  }
> = {
  totp: {
    title: "Enter your authentication code",
    description:
      "Open your authenticator app and enter the 6-digit code for MTI 360.",
    label: "Authentication code",
    field: "code",
    path: "/mfa/verify",
    missing: "Enter the 6-digit code from your authenticator app.",
    invalid:
      "That code didn't work. Check your authenticator app and try again.",
  },
  recovery: {
    title: "Enter a recovery code",
    description:
      "Use one of the recovery codes you saved when you set up two-step verification. Each code works once.",
    label: "Recovery code",
    field: "recovery_code",
    path: "/mfa/recovery",
    missing: "Enter one of your recovery codes.",
    invalid: "That recovery code didn't work. Check it and try again.",
  },
};

export type MfaStepProps = {
  csrfToken: string;
  next: string | null;
  /** Back to the sign-in form, optionally with a notice. */
  onRestart: (feedback: Feedback | null) => void;
};

export function MfaStep({ csrfToken, next, onRestart }: MfaStepProps) {
  const inputId = useId();
  const [mode, setMode] = useState<Mode>("totp");
  const [code, setCode] = useState("");
  const [pending, setPending] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [invalid, setInvalid] = useState(false);
  const copy = COPY[mode];

  const switchMode = (value: Mode) => {
    setMode(value);
    setCode("");
    setInvalid(false);
    setFeedback(null);
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending) return;
    setPending(true);
    setFeedback(null);
    setInvalid(false);
    try {
      const session = await authPost<SessionWire>(
        copy.path,
        { [copy.field]: code.trim() },
        { csrfToken },
      );
      setCode("");
      assignLocation(destinationFor(session.status, next));
      return;
    } catch (error) {
      setCode("");
      setPending(false);
      if (error instanceof ApiError && error.status === 401) {
        onRestart(MFA_ENDED);
        return;
      }
      if (error instanceof ApiError && error.code === "VALIDATION_ERROR") {
        setInvalid(true);
      } else {
        setFeedback(commonFeedback(error, tooManyAttempts));
      }
      document.getElementById(inputId)?.focus();
    }
  };

  const restart = () => {
    // Ends the pending session; the result does not matter.
    void authPost("/logout").catch(() => undefined);
    onRestart(null);
  };

  return (
    <AuthenticationTemplate
      title={copy.title}
      description={copy.description}
      footer={
        <Button variant="tertiary" onPress={restart}>
          Back to sign in
        </Button>
      }
    >
      <FeedbackRegion feedback={feedback} />
      <Form
        key={mode}
        aria-label={copy.title}
        onSubmit={(event) => void submit(event)}
      >
        <RequiredLegend />
        <Input
          id={inputId}
          label={copy.label}
          name={copy.field}
          isRequired
          autoComplete={mode === "totp" ? "one-time-code" : "off"}
          inputMode={mode === "totp" ? "numeric" : "text"}
          autoCapitalize="none"
          spellCheck="false"
          maxLength={mode === "totp" ? 7 : 13}
          value={code}
          onChange={(value) => {
            setCode(value);
            setInvalid(false);
          }}
          isInvalid={invalid || undefined}
          errorMessage={invalid ? copy.invalid : copy.missing}
        />
        <Button type="submit" size="lg" fullWidth isPending={pending}>
          {pending ? "Verifying…" : "Verify"}
        </Button>
        <div>
          <Button
            variant="tertiary"
            onPress={() => switchMode(mode === "totp" ? "recovery" : "totp")}
          >
            {mode === "totp"
              ? "Use a recovery code instead"
              : "Use your authenticator app instead"}
          </Button>
        </div>
      </Form>
    </AuthenticationTemplate>
  );
}
