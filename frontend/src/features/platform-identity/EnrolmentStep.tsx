"use client";

import { useEffect, useId, useRef, useState, type FormEvent } from "react";

import {
  Alert,
  Button,
  CopyButton,
  Form,
  SecretValue,
} from "@/design-system/components";
import { focusRing } from "@/design-system/lib/cx";
import { AuthenticationTemplate } from "@/design-system/templates/AuthenticationTemplate";
import { FeedbackRegion, RequiredLegend } from "@/features/identity/components";
import {
  commonFeedback,
  tooManyAttempts,
  type Feedback,
} from "@/features/identity/feedback";
import { MfaCodeField } from "@/features/identity/MfaCodeField";
import { MFA_ENDED } from "@/features/identity/MfaStep";
import { PLATFORM_CONTEXT } from "@/features/identity/realm";
import { ApiError } from "@/lib/api/errors";
import type {
  MfaEnrolmentConfirmedWire,
  MfaEnrolmentWire,
} from "@/lib/api/types";
import { assignLocation } from "@/lib/session/document";
import { platformAuthPost } from "@/lib/session/platform-client";
import { resolvePlatformNext } from "@/lib/session/platform-routes";

import { RecoveryCodesPanel, RECOVERY_CODES_TITLE } from "./RecoveryCodesPanel";

// PAUTH-04 Set up two-step verification (T01-09B UI contract §6; D9B-3,
// D9B-4). Runs after a password sign-in that answered
// `mfa_enrolment_required`: the first sign-in after an invitation or the
// bootstrap CLI, and the next sign-in after an MFA reset. The pending
// session's CSRF token is in memory only (D9B-2).
//
// Enrolment starts ONLY on the explicit "Set up authenticator app" press —
// never on mount: every POST /enrolment replaces the unconfirmed secret, so
// a React StrictMode double effect would silently replace it.
//
// The secret and the otpauth:// URI live only in this component's state.
// They are dropped the moment the confirmation succeeds (the state becomes
// the recovery codes) and on unmount; they are never stored, logged, put in
// a URL or the title. No QR code (ADR-0017). Confirmation rotates the session
// and returns the recovery codes once (PAUTH-05).

export const ENROLMENT_ENDED: Feedback = {
  tone: "warning",
  title: "Set-up ended. Sign in again.",
  body: "Remove the MTI 360 entry you added to your authenticator app — a new key will be issued.",
};

const TIME_LIMIT =
  "Finish within 5 minutes of signing in, or you'll need to sign in again.";

type Phase =
  | { step: "intro" }
  | { step: "key"; enrolment: MfaEnrolmentWire }
  | { step: "codes"; codes: string[] };

export type EnrolmentStepProps = {
  csrfToken: string;
  next: string | null;
  onRestart: (feedback: Feedback | null) => void;
};

export function EnrolmentStep({
  csrfToken,
  next,
  onRestart,
}: EnrolmentStepProps) {
  const codeId = useId();
  const titleRef = useRef<HTMLHeadingElement>(null);
  const [phase, setPhase] = useState<Phase>({ step: "intro" });
  const [code, setCode] = useState("");
  const [invalid, setInvalid] = useState(false);
  const [pending, setPending] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);

  useEffect(() => {
    titleRef.current?.focus();
  }, [phase.step]);

  /** 401: the pending session ended (5 minutes or too many codes). */
  const ended = (error: unknown) =>
    error instanceof ApiError && error.status === 401;

  const start = async () => {
    if (pending) return;
    setPending(true);
    setFeedback(null);
    try {
      const enrolment = await platformAuthPost<MfaEnrolmentWire>(
        "/mfa/enrolment",
        undefined,
        { csrfToken },
      );
      setPending(false);
      setPhase({ step: "key", enrolment });
    } catch (error) {
      setPending(false);
      if (ended(error)) {
        onRestart(MFA_ENDED);
        return;
      }
      if (error instanceof ApiError && error.code === "CONFLICT") {
        // Already set up (another tab finished): sign in normally.
        onRestart(MFA_ENDED);
        return;
      }
      setFeedback(commonFeedback(error, tooManyAttempts));
    }
  };

  const confirm = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending) return;
    setPending(true);
    setFeedback(null);
    setInvalid(false);
    try {
      const confirmed = await platformAuthPost<MfaEnrolmentConfirmedWire>(
        "/mfa/enrolment/confirm",
        { code: code.trim() },
        { csrfToken },
      );
      setCode("");
      setPending(false);
      // Replacing the phase drops the secret and the URI from memory.
      setPhase({ step: "codes", codes: confirmed.recovery_codes });
    } catch (error) {
      setCode("");
      setPending(false);
      if (ended(error)) {
        onRestart(ENROLMENT_ENDED);
        return;
      }
      if (error instanceof ApiError && error.code === "VALIDATION_ERROR") {
        setInvalid(true);
      } else {
        setFeedback(commonFeedback(error, tooManyAttempts));
      }
      document.getElementById(codeId)?.focus();
    }
  };

  const restart = () => {
    // Ends the pending session; the result does not matter.
    void platformAuthPost("/logout").catch(() => undefined);
    onRestart(null);
  };

  const backToSignIn = (
    <Button variant="tertiary" onPress={restart}>
      Back to sign in
    </Button>
  );

  if (phase.step === "codes") {
    return (
      <AuthenticationTemplate
        title={RECOVERY_CODES_TITLE}
        titleRef={titleRef}
        context={PLATFORM_CONTEXT}
        description="Two-step verification is on. Keep these codes somewhere safe and separate from your authenticator app."
      >
        <RecoveryCodesPanel
          codes={phase.codes}
          onContinue={() => {
            setPhase({ step: "intro" });
            assignLocation(resolvePlatformNext(next));
          }}
        />
      </AuthenticationTemplate>
    );
  }

  if (phase.step === "intro") {
    return (
      <AuthenticationTemplate
        title="Set up two-step verification"
        titleRef={titleRef}
        context={PLATFORM_CONTEXT}
        description="Your authenticator app is required every time you sign in to MTI 360 platform administration."
        footer={backToSignIn}
      >
        <Alert tone="info" title={TIME_LIMIT} />
        <FeedbackRegion feedback={feedback} />
        <p className="text-body-sm text-text-primary">
          You&apos;ll need an authenticator app on your phone or computer that
          supports time-based codes. You&apos;ll add MTI 360 to it with a setup
          key, then enter the code it shows.
        </p>
        <Button
          size="lg"
          fullWidth
          isPending={pending}
          onPress={() => void start()}
        >
          {pending ? "Preparing…" : "Set up authenticator app"}
        </Button>
      </AuthenticationTemplate>
    );
  }

  const { secret, otpauth_uri: uri } = phase.enrolment;

  return (
    <AuthenticationTemplate
      title="Add MTI 360 to your authenticator app"
      titleRef={titleRef}
      context={PLATFORM_CONTEXT}
      description={TIME_LIMIT}
      footer={backToSignIn}
    >
      <FeedbackRegion feedback={feedback} />
      <ol className="flex list-decimal flex-col gap-4 pl-5 text-body-sm text-text-primary">
        <li>
          <div className="flex flex-col gap-3">
            <span>
              In your authenticator app, add an account and choose to enter a
              setup key.
            </span>
            <SecretValue
              label="Setup key"
              value={secret}
              actions={<CopyButton value={secret} label="Copy key" size="sm" />}
            />
            <a
              href={uri}
              className={`w-fit rounded-sm text-link underline-offset-4 hover:underline ${focusRing}`}
            >
              Open in authenticator app
            </a>
            <dl className="flex flex-col gap-1 text-text-secondary">
              {[
                ["Type", "Time-based"],
                ["Digits", "6"],
                ["Interval", "30 seconds"],
              ].map(([term, value]) => (
                <div key={term} className="flex gap-2">
                  <dt>{term}:</dt>
                  <dd className="text-text-primary">{value}</dd>
                </div>
              ))}
            </dl>
          </div>
        </li>
        <li>Enter the 6-digit code your app now shows for MTI 360.</li>
      </ol>
      <Form
        aria-label="Confirm your authenticator app"
        onSubmit={(event) => void confirm(event)}
      >
        <RequiredLegend />
        <MfaCodeField
          id={codeId}
          label="Code from your authenticator app"
          description="If you have more than one MTI 360 entry, use the one you just added."
          value={code}
          onChange={(value) => {
            setCode(value);
            setInvalid(false);
          }}
          invalid={invalid}
          invalidMessage="That code didn't work. Check the entry you just added and try again."
          missingMessage="Enter the 6-digit code from your authenticator app."
        />
        <Button type="submit" size="lg" fullWidth isPending={pending}>
          {pending ? "Verifying…" : "Verify and turn on"}
        </Button>
      </Form>
    </AuthenticationTemplate>
  );
}
