"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import { Alert, Button, Form, Input } from "@/design-system/components";
import { AuthenticationTemplate } from "@/design-system/templates/AuthenticationTemplate";

import {
  emailError,
  EMAIL_MAX_LENGTH,
  FeedbackRegion,
  RequiredLegend,
} from "./components";
import { commonFeedback, type Feedback } from "./feedback";
import { AUTH_REALMS, type AuthRealm } from "./realm";

// AUTH-02 Forgot password (T01-04 UI contract §8.2). ANY 2xx shows the same
// confirmation — the UI never says whether an account exists (S2, S3); the
// API answers 202 for every email after the same minimum delay. The echoed
// email is what the person typed (escaped text), never server data, and it
// is never put in a URL (S10). T01-09B: `realm="platform"` is PAUTH-01
// (/platform/forgot-password; POST /platform/auth/password-reset).

const COPY: Record<AuthRealm, { description: string; account: string }> = {
  tenant: {
    description:
      "Enter the email address you use for MTI 360. If it matches an account, we'll send a link to choose a new password.",
    account: "an account",
  },
  platform: {
    description:
      "Enter the email address of your MTI 360 platform account. If it matches an account, we'll send a link to choose a new password.",
    account: "a platform account",
  },
};

export function ForgotPasswordScreen({
  realm = "tenant",
}: {
  realm?: AuthRealm;
}) {
  const target = AUTH_REALMS[realm];
  const copy = COPY[realm];
  const [email, setEmail] = useState("");
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const confirmationRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (sentTo !== null) confirmationRef.current?.focus();
  }, [sentTo]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending) return;
    const address = email.trim();
    setPending(true);
    setFeedback(null);
    try {
      await target.post("/password-reset", { email: address });
      setSentTo(address);
    } catch (error) {
      setFeedback(commonFeedback(error));
    } finally {
      setPending(false);
    }
  };

  const chooseDifferentEmail = () => {
    setEmail("");
    setSentTo(null);
  };

  return (
    <AuthenticationTemplate
      title="Reset your password"
      description={copy.description}
      context={target.context}
      footer={
        <Button variant="tertiary" href={target.routes.login}>
          Back to sign in
        </Button>
      }
    >
      {sentTo !== null ? (
        <div
          ref={confirmationRef}
          tabIndex={-1}
          // a11y-focus: replaced content; receives programmatic focus only
          className="flex flex-col gap-4 outline-none"
        >
          <Alert tone="info" title="Check your email">
            If {copy.account} uses{" "}
            <strong className="break-all">{sentTo}</strong>, we&apos;ve sent a
            link to reset the password. The link expires in 30 minutes. Check
            your spam folder if you don&apos;t see it.
          </Alert>
          <div>
            <Button variant="secondary" onPress={chooseDifferentEmail}>
              Use a different email
            </Button>
          </div>
        </div>
      ) : (
        <>
          <FeedbackRegion feedback={feedback} />
          <Form
            aria-label="Reset your password"
            onSubmit={(event) => void submit(event)}
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
            <Button type="submit" size="lg" fullWidth isPending={pending}>
              {pending ? "Sending…" : "Send reset link"}
            </Button>
          </Form>
        </>
      )}
    </AuthenticationTemplate>
  );
}
