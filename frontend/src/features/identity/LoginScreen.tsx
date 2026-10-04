"use client";

import { useId, useState, type FormEvent, type KeyboardEvent } from "react";

import { Alert, Button, Form, Input } from "@/design-system/components";
import { AuthenticationTemplate } from "@/design-system/templates/AuthenticationTemplate";
import { ApiError } from "@/lib/api/errors";
import type { SessionWire } from "@/lib/api/types";
import { authPost } from "@/lib/session/client";
import { assignLocation } from "@/lib/session/document";
import {
  AUTH_ROUTES,
  destinationFor,
  type LoginReason,
} from "@/lib/session/routes";

import {
  emailError,
  EMAIL_MAX_LENGTH,
  FeedbackRegion,
  RequiredLegend,
} from "./components";
import {
  commonFeedback,
  SIGN_IN_FAILED,
  tooManyAttempts,
  type Feedback,
} from "./feedback";
import { MfaStep } from "./MfaStep";

// AUTH-01 Sign in (T01-04 UI contract §8.1). Email and password are sent
// once, in the POST body, and the password lives only in this component's
// state: it is cleared after every failed attempt and never stored, logged or
// put in a URL. Every refused sign-in renders the SAME DOM (S2, S8). When the
// account has MFA, the API answers `mfa_required` with an MFA-pending session;
// the code step then runs in place (MfaStep), with that response's CSRF token
// kept in memory only. Success is a full document navigation (§6.2).

const NOTICES: Record<LoginReason, string> = {
  "signed-out": "You've signed out.",
  "password-reset":
    "Your password has been changed. Sign in with your new password.",
  "invitation-accepted": "Invitation accepted. Sign in to continue.",
};

export type LoginScreenProps = {
  reason: LoginReason | null;
  /** Validated `next` (or null): carried to the next step. */
  next: string | null;
};

export function LoginScreen({ reason, next }: LoginScreenProps) {
  const passwordId = useId();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [capsLock, setCapsLock] = useState(false);
  const [pending, setPending] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [mfaToken, setMfaToken] = useState<string | null>(null);

  const failed = (outcome: Feedback) => {
    setFeedback(outcome);
    setPassword("");
    setPending(false);
    document.getElementById(passwordId)?.focus();
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending) return;
    setPending(true);
    setFeedback(null);
    try {
      const session = await authPost<SessionWire>("/login", {
        email: email.trim(),
        password,
      });
      setPassword("");
      if (session.status === "mfa_required") {
        setPending(false);
        setMfaToken(session.csrf_token);
        return;
      }
      assignLocation(destinationFor(session.status, next));
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        failed(SIGN_IN_FAILED);
      } else {
        failed(commonFeedback(error, tooManyAttempts));
      }
    }
  };

  const trackCapsLock = (event: KeyboardEvent) =>
    setCapsLock(event.getModifierState("CapsLock"));

  if (mfaToken) {
    return (
      <MfaStep
        csrfToken={mfaToken}
        next={next}
        onRestart={(outcome) => {
          setMfaToken(null);
          setFeedback(outcome);
        }}
      />
    );
  }

  return (
    <AuthenticationTemplate
      title="Sign in to MTI 360"
      description="Use the email address your institute invited."
      footer={
        <p className="text-body-sm text-text-secondary">
          Need access? Ask your institute administrator to invite you.
        </p>
      }
    >
      {reason && <Alert tone="success" title={NOTICES[reason]} />}
      <FeedbackRegion feedback={feedback} />
      <Form onSubmit={(event) => void submit(event)} aria-label="Sign in">
        <RequiredLegend />
        <Input
          label="Email"
          name="email"
          type="email"
          autoComplete="username"
          inputMode="email"
          autoCapitalize="none"
          spellCheck="false"
          maxLength={EMAIL_MAX_LENGTH}
          isRequired
          value={email}
          onChange={setEmail}
          errorMessage={emailError}
        />
        <Input
          id={passwordId}
          label="Password"
          name="password"
          type="password"
          isRevealable
          autoComplete="current-password"
          maxLength={128}
          isRequired
          value={password}
          onChange={setPassword}
          onKeyDown={trackCapsLock}
          onKeyUp={trackCapsLock}
          onBlur={() => setCapsLock(false)}
          description={
            <span aria-live="polite">{capsLock ? "Caps Lock is on." : ""}</span>
          }
          errorMessage="Enter your password."
        />
        <div>
          <Button variant="tertiary" href={AUTH_ROUTES.forgotPassword}>
            Forgot password?
          </Button>
        </div>
        <Button type="submit" size="lg" fullWidth isPending={pending}>
          {pending ? "Signing in…" : "Sign in"}
        </Button>
      </Form>
    </AuthenticationTemplate>
  );
}
