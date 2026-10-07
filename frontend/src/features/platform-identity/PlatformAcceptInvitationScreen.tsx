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
import {
  confirmPasswordError,
  FeedbackRegion,
  newPasswordError,
  PASSWORD_MAX_LENGTH,
  PasswordRequirements,
  passwordLengthError,
  RequiredLegend,
} from "@/features/identity/components";
import {
  commonFeedback,
  passwordFieldError,
  tooManyRequests,
  type Feedback,
} from "@/features/identity/feedback";
import { AUTH_REALMS, PLATFORM_CONTEXT } from "@/features/identity/realm";
import { useFragmentToken } from "@/features/identity/useFragmentToken";
import { ApiError } from "@/lib/api/errors";
import type { PlatformInvitationPreviewWire } from "@/lib/api/types";
import { assignLocation } from "@/lib/session/document";
import { platformAuthPost } from "@/lib/session/platform-client";
import { PLATFORM_AUTH_ROUTES } from "@/lib/session/platform-routes";

// PAUTH-03 Accept a platform invitation (T01-09B UI contract §7; D7-3). The
// T01-09A fragment pattern: the token is read from #token=, removed from the
// address bar at once, kept in memory and sent only in the preview and accept
// POST bodies. The preview returns only the server-masked email (shown as
// escaped text). Unknown, expired, revoked and used invitations are one 404
// message. Accepting sets the first password only; it never signs anyone in:
// the first sign-in then sets up two-step verification (PAUTH-04).

type Preview =
  | { state: "loading" }
  | { state: "ready"; email: string }
  | { state: "unusable" }
  | { state: "rate-limited"; feedback: Feedback }
  | { state: "failed" };

const LOGIN_AFTER_ACCEPT = AUTH_REALMS.platform.loginUrl({
  reason: "invitation-accepted",
});

const BACK_TO_SIGN_IN = (
  <Button variant="tertiary" href={PLATFORM_AUTH_ROUTES.login}>
    Back to sign in
  </Button>
);

const isUnusable = (error: unknown) =>
  error instanceof ApiError &&
  (error.code === "NOT_FOUND" ||
    (error.code === "VALIDATION_ERROR" && error.hasField("token")));

async function previewInvitation(token: string): Promise<Preview> {
  try {
    const data = await platformAuthPost<PlatformInvitationPreviewWire>(
      "/invitations/preview",
      { token },
    );
    return { state: "ready", email: data.email };
  } catch (error) {
    if (isUnusable(error)) return { state: "unusable" };
    if (error instanceof ApiError && error.status === 429) {
      return {
        state: "rate-limited",
        feedback: tooManyRequests(error, "reload this page"),
      };
    }
    return { state: "failed" };
  }
}

export function PlatformAcceptInvitationScreen() {
  const token = useFragmentToken();
  const passwordId = useId();
  const requirementsId = useId();
  const [preview, setPreview] = useState<Preview>({ state: "loading" });
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [pending, setPending] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const replacedTitle = useRef<HTMLHeadingElement>(null);
  const interacted = useRef(false);

  // One preview per page load (no side effects; "Try again" repeats it).
  useEffect(() => {
    if (!token) return;
    void previewInvitation(token).then(setPreview);
  }, [token]);

  useEffect(() => {
    if (interacted.current && preview.state === "unusable") {
      replacedTitle.current?.focus();
    }
  }, [preview.state]);

  const clearPasswords = () => {
    setPassword("");
    setConfirmation("");
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending || !token) return;
    interacted.current = true;
    setPending(true);
    setFeedback(null);
    setFieldErrors({});
    try {
      await platformAuthPost("/invitations/accept", { token, password });
      clearPasswords();
      assignLocation(LOGIN_AFTER_ACCEPT);
      return;
    } catch (error) {
      clearPasswords();
      setPending(false);
      if (isUnusable(error)) {
        setPreview({ state: "unusable" });
        return;
      }
      if (error instanceof ApiError && error.hasField("password")) {
        setFieldErrors({
          password: passwordFieldError(error.fieldCode("password")),
        });
        document.getElementById(passwordId)?.focus();
        return;
      }
      setFeedback(
        commonFeedback(error, (limited) =>
          tooManyRequests(limited, "reload this page"),
        ),
      );
    }
  };

  if (token === null) {
    return (
      <AuthenticationTemplate
        context={PLATFORM_CONTEXT}
        footer={BACK_TO_SIGN_IN}
      >
        <ErrorState
          titleAs="h1"
          title="This invitation link is incomplete"
          description="Open the link from your invitation email again."
        />
      </AuthenticationTemplate>
    );
  }

  if (preview.state === "unusable") {
    return (
      <AuthenticationTemplate
        context={PLATFORM_CONTEXT}
        footer={BACK_TO_SIGN_IN}
      >
        <ErrorState
          titleAs="h1"
          titleRef={replacedTitle}
          title="This invitation can't be used"
          description="It may have expired, been withdrawn or already been accepted. Ask a Super Admin to send a new invitation."
        />
      </AuthenticationTemplate>
    );
  }

  if (preview.state === "failed") {
    return (
      <AuthenticationTemplate
        context={PLATFORM_CONTEXT}
        footer={BACK_TO_SIGN_IN}
      >
        <ErrorState
          titleAs="h1"
          title="We couldn't check your invitation"
          description="Something went wrong while checking your invitation. Try again in a moment."
          onRetry={() => {
            if (!token) return;
            setPreview({ state: "loading" });
            void previewInvitation(token).then(setPreview);
          }}
        />
      </AuthenticationTemplate>
    );
  }

  if (token === undefined || preview.state === "loading") {
    return (
      <AuthenticationTemplate
        title="Accept your invitation"
        context={PLATFORM_CONTEXT}
      >
        <LoadingRegion label="Checking your invitation">
          <SkeletonText lines={3} />
        </LoadingRegion>
      </AuthenticationTemplate>
    );
  }

  if (preview.state === "rate-limited") {
    return (
      <AuthenticationTemplate
        title="Accept your invitation"
        context={PLATFORM_CONTEXT}
        footer={BACK_TO_SIGN_IN}
      >
        <FeedbackRegion feedback={preview.feedback} />
      </AuthenticationTemplate>
    );
  }

  return (
    <AuthenticationTemplate
      title="Join MTI 360 platform administration"
      description={`Invitation for ${preview.email}`}
      context={PLATFORM_CONTEXT}
      footer={BACK_TO_SIGN_IN}
    >
      <p className="text-body-sm text-text-primary">
        Choose a password. When you first sign in, you&apos;ll set up an
        authenticator app — it&apos;s required every time you sign in.
      </p>
      <PasswordRequirements id={requirementsId} />
      <FeedbackRegion feedback={feedback} />
      <Form
        aria-label="Choose your password"
        validationErrors={fieldErrors}
        onSubmit={(event) => void submit(event)}
      >
        <RequiredLegend />
        <Input
          id={passwordId}
          label="Create password"
          name="password"
          type="password"
          isRevealable
          autoComplete="new-password"
          maxLength={PASSWORD_MAX_LENGTH}
          isRequired
          isReadOnly={pending}
          aria-describedby={requirementsId}
          value={password}
          onChange={setPassword}
          validate={(value) => (value ? passwordLengthError(value) : null)}
          errorMessage={newPasswordError}
        />
        <Input
          label="Confirm password"
          name="confirm_password"
          type="password"
          isRevealable
          autoComplete="new-password"
          isRequired
          isReadOnly={pending}
          value={confirmation}
          onChange={setConfirmation}
          validate={(value) =>
            value && value !== password ? "The passwords don't match." : null
          }
          errorMessage={confirmPasswordError}
        />
        <Button type="submit" size="lg" fullWidth isPending={pending}>
          {pending ? "Accepting…" : "Accept invitation"}
        </Button>
      </Form>
    </AuthenticationTemplate>
  );
}
