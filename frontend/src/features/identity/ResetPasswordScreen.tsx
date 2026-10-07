"use client";

import { useEffect, useId, useRef, useState, type FormEvent } from "react";

import {
  Button,
  ErrorState,
  Form,
  Input,
  LoadingRegion,
  SkeletonText,
} from "@/design-system/components";
import { AuthenticationTemplate } from "@/design-system/templates/AuthenticationTemplate";
import { ApiError } from "@/lib/api/errors";
import { assignLocation } from "@/lib/session/document";

import {
  confirmPasswordError,
  FeedbackRegion,
  newPasswordError,
  PASSWORD_MAX_LENGTH,
  PasswordRequirements,
  passwordLengthError,
  RequiredLegend,
} from "./components";
import { commonFeedback, passwordFieldError, type Feedback } from "./feedback";
import { AUTH_REALMS, type AuthRealm } from "./realm";
import { useFragmentToken } from "./useFragmentToken";

// AUTH-03 Reset password (T01-04 UI contract §8.3). The token comes from the
// URL fragment (useFragmentToken) and is sent only in the POST body. The
// page never shows it; a reload after the fragment was removed shows "This
// reset link is incomplete", which is safe. Invalid, expired and used links
// are one message (OQ-6). Passwords are cleared after every failure.

// T01-09B: `realm="platform"` is PAUTH-02 (/platform/reset-password#token=;
// POST /platform/auth/password-reset/confirm). A platform reset never
// bypasses MFA (D6-2), and the copy says so.

const DESCRIPTIONS: Record<AuthRealm, string> = {
  tenant:
    "Your new password replaces the old one and signs you out everywhere.",
  platform:
    "Your new password replaces the old one and signs you out everywhere. Your authenticator app is still required when you sign in.",
};

export function ResetPasswordScreen({
  realm = "tenant",
}: {
  realm?: AuthRealm;
}) {
  const target = AUTH_REALMS[realm];
  const backToSignIn = (
    <Button variant="tertiary" href={target.routes.login}>
      Back to sign in
    </Button>
  );
  const token = useFragmentToken();
  const newPasswordId = useId();
  const requirementsId = useId();
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [pending, setPending] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [unusable, setUnusable] = useState(false);
  const unusableTitle = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    if (unusable) unusableTitle.current?.focus();
  }, [unusable]);

  const clearPasswords = () => {
    setPassword("");
    setConfirmation("");
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending || !token) return;
    setPending(true);
    setFeedback(null);
    setFieldErrors({});
    try {
      await target.post("/password-reset/confirm", {
        token,
        new_password: password,
      });
      clearPasswords();
      assignLocation(target.loginUrl({ reason: "password-reset" }));
      return;
    } catch (error) {
      clearPasswords();
      setPending(false);
      if (
        error instanceof ApiError &&
        (error.code === "NOT_FOUND" ||
          (error.code === "VALIDATION_ERROR" && error.hasField("token")))
      ) {
        setUnusable(true);
        return;
      }
      if (error instanceof ApiError && error.hasField("new_password")) {
        setFieldErrors({
          new_password: passwordFieldError(error.fieldCode("new_password")),
        });
        document.getElementById(newPasswordId)?.focus();
        return;
      }
      setFeedback(commonFeedback(error));
    }
  };

  if (token === undefined) {
    return (
      <AuthenticationTemplate
        title="Choose a new password"
        context={target.context}
      >
        <LoadingRegion label="Checking your reset link">
          <SkeletonText lines={3} />
        </LoadingRegion>
      </AuthenticationTemplate>
    );
  }

  if (token === null) {
    return (
      <AuthenticationTemplate context={target.context} footer={backToSignIn}>
        <ErrorState
          titleAs="h1"
          title="This reset link is incomplete"
          description="Open the link from your email again, or request a new one."
          backHref={target.routes.forgotPassword}
          backLabel="Request a new link"
        />
      </AuthenticationTemplate>
    );
  }

  if (unusable) {
    return (
      <AuthenticationTemplate context={target.context} footer={backToSignIn}>
        <ErrorState
          titleAs="h1"
          titleRef={unusableTitle}
          title="This reset link can't be used"
          description="It may have expired or already been used. Reset links work once and expire after 30 minutes."
          backHref={target.routes.forgotPassword}
          backLabel="Request a new link"
        />
      </AuthenticationTemplate>
    );
  }

  return (
    <AuthenticationTemplate
      title="Choose a new password"
      description={DESCRIPTIONS[realm]}
      context={target.context}
      footer={backToSignIn}
    >
      <PasswordRequirements id={requirementsId} />
      <FeedbackRegion feedback={feedback} />
      <Form
        aria-label="Choose a new password"
        validationErrors={fieldErrors}
        onSubmit={(event) => void submit(event)}
      >
        <RequiredLegend />
        <Input
          id={newPasswordId}
          label="New password"
          name="new_password"
          type="password"
          isRevealable
          autoComplete="new-password"
          maxLength={PASSWORD_MAX_LENGTH}
          isRequired
          aria-describedby={requirementsId}
          value={password}
          onChange={setPassword}
          validate={(value) => (value ? passwordLengthError(value) : null)}
          errorMessage={newPasswordError}
        />
        <Input
          label="Confirm new password"
          name="confirm_password"
          type="password"
          isRevealable
          autoComplete="new-password"
          isRequired
          value={confirmation}
          onChange={setConfirmation}
          validate={(value) =>
            value && value !== password ? "The passwords don't match." : null
          }
          errorMessage={confirmPasswordError}
        />
        <Button type="submit" size="lg" fullWidth isPending={pending}>
          {pending ? "Changing password…" : "Change password"}
        </Button>
      </Form>
    </AuthenticationTemplate>
  );
}
