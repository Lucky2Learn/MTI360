"use client";

import { useId, useState, type FormEvent, type KeyboardEvent } from "react";

import { Alert, Button, Form, Input } from "@/design-system/components";
import { AuthenticationTemplate } from "@/design-system/templates/AuthenticationTemplate";
import {
  emailError,
  EMAIL_MAX_LENGTH,
  FeedbackRegion,
  RequiredLegend,
} from "@/features/identity/components";
import {
  commonFeedback,
  tooManyAttempts,
  type Feedback,
} from "@/features/identity/feedback";
import { MfaStep } from "@/features/identity/MfaStep";
import { PLATFORM_CONTEXT } from "@/features/identity/realm";
import { ApiError } from "@/lib/api/errors";
import type { PlatformSessionWire } from "@/lib/api/types";
import { assignLocation } from "@/lib/session/document";
import { platformAuthPost } from "@/lib/session/platform-client";
import {
  PLATFORM_AUTH_ROUTES,
  resolvePlatformNext,
  type PlatformLoginReason,
} from "@/lib/session/platform-routes";

import { EnrolmentStep } from "./EnrolmentStep";

// PLAT-01 Platform sign-in (T01-09B UI contract §6). Email and password are
// sent once, in the POST body, to /platform/auth/login; the password lives
// only in this component's state and is cleared after every failure. Every
// refusal renders the SAME DOM: no "unknown account", "locked" or
// "suspended" (S2, S8). A correct password opens an MFA-pending session
// whose status and CSRF token exist only in this response, so the next step
// runs in place and is never restored after a reload (D9B-2):
// `mfa_required` → PLAT-02 (MfaStep, platform realm);
// `mfa_enrolment_required` → PAUTH-04 (EnrolmentStep).
// No cross-link to the institute sign-in (D9B-11).

const NOTICES: Record<PlatformLoginReason, string> = {
  "signed-out": "You've signed out.",
  "password-reset":
    "Your password has been changed. Sign in with your new password and your authenticator app.",
  "invitation-accepted":
    "Your password is set. Sign in to set up two-step verification.",
};

/** One message for every refused sign-in (S2, S8). */
export const PLATFORM_SIGN_IN_FAILED: Feedback = {
  tone: "error",
  title: "We couldn't sign you in",
  body: "Check your email and password and try again. If the problem continues, contact your security team.",
};

type Step =
  | { kind: "password" }
  | { kind: "verify"; csrfToken: string }
  | { kind: "enrol"; csrfToken: string };

export type PlatformLoginScreenProps = {
  reason: PlatformLoginReason | null;
  /** Validated platform `next` (or null). */
  next: string | null;
};

export function PlatformLoginScreen({
  reason,
  next,
}: PlatformLoginScreenProps) {
  const passwordId = useId();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [capsLock, setCapsLock] = useState(false);
  const [pending, setPending] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [step, setStep] = useState<Step>({ kind: "password" });

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
      const session = await platformAuthPost<PlatformSessionWire>("/login", {
        email: email.trim(),
        password,
      });
      setPassword("");
      setPending(false);
      if (session.status === "mfa_required") {
        setStep({ kind: "verify", csrfToken: session.csrf_token });
        return;
      }
      if (session.status === "mfa_enrolment_required") {
        setStep({ kind: "enrol", csrfToken: session.csrf_token });
        return;
      }
      // Not expected (the password step never completes MFA); the shell's
      // server gate decides either way.
      assignLocation(resolvePlatformNext(next));
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        failed(PLATFORM_SIGN_IN_FAILED);
      } else {
        failed(commonFeedback(error, tooManyAttempts));
      }
    }
  };

  const restart = (outcome: Feedback | null) => {
    setStep({ kind: "password" });
    setFeedback(outcome);
  };

  const trackCapsLock = (event: KeyboardEvent) =>
    setCapsLock(event.getModifierState("CapsLock"));

  if (step.kind === "verify") {
    return (
      <MfaStep
        realm="platform"
        csrfToken={step.csrfToken}
        next={next}
        onRestart={restart}
      />
    );
  }

  if (step.kind === "enrol") {
    return (
      <EnrolmentStep
        csrfToken={step.csrfToken}
        next={next}
        onRestart={restart}
      />
    );
  }

  return (
    <AuthenticationTemplate
      title="Sign in to platform administration"
      description="For MTI 360 platform administrators. You'll also need your authenticator app."
      context={PLATFORM_CONTEXT}
      footer={
        <p className="text-body-sm text-text-secondary">
          Platform access is by invitation only.
        </p>
      }
    >
      {reason && <Alert tone="success" title={NOTICES[reason]} />}
      <FeedbackRegion feedback={feedback} />
      <Form
        onSubmit={(event) => void submit(event)}
        aria-label="Sign in to platform administration"
      >
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
          <Button variant="tertiary" href={PLATFORM_AUTH_ROUTES.forgotPassword}>
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
