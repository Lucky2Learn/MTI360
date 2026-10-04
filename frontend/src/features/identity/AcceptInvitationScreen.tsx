"use client";

import { useEffect, useId, useRef, useState, type FormEvent } from "react";

import {
  Alert,
  Button,
  ErrorState,
  Form,
  Input,
  LoadingRegion,
  SkeletonText,
} from "@/design-system/components";
import { AuthenticationTemplate } from "@/design-system/templates/AuthenticationTemplate";
import { ApiError } from "@/lib/api/errors";
import type { InvitationPreviewWire } from "@/lib/api/types";
import { authPost, readSession, signOut } from "@/lib/session/client";
import { assignLocation } from "@/lib/session/document";
import { AUTH_ROUTES, authUrl } from "@/lib/session/routes";

import {
  confirmPasswordError,
  FeedbackRegion,
  newPasswordError,
  PASSWORD_MAX_LENGTH,
  PasswordRequirements,
  passwordLengthError,
  RequiredLegend,
} from "./components";
import {
  commonFeedback,
  passwordFieldError,
  tooManyRequests,
  type Feedback,
} from "./feedback";
import { useFragmentToken } from "./useFragmentToken";

// AUTH-06 Accept invitation (T01-04 UI contract §8.4; D19). The token comes
// from the URL fragment and is sent only in the preview and accept POST
// bodies. The preview returns only the institute name, the server-masked
// email and "new" | "existing"; both are shown as escaped text. Every 404
// (unknown, expired, withdrawn, accepted, membership revoked, institute
// unavailable) is one message. Accepting never signs anyone in, and an
// existing account never sees a password field.

type Preview =
  | { state: "loading" }
  | { state: "ready"; data: InvitationPreviewWire }
  | { state: "unusable" }
  | { state: "rate-limited"; feedback: Feedback }
  | { state: "failed" };

const LOGIN_AFTER_ACCEPT = authUrl(AUTH_ROUTES.login, {
  reason: "invitation-accepted",
});

const BACK_TO_SIGN_IN = (
  <Button variant="tertiary" href={AUTH_ROUTES.login}>
    Back to sign in
  </Button>
);

const isUnusable = (error: unknown) =>
  error instanceof ApiError &&
  (error.code === "NOT_FOUND" ||
    (error.code === "VALIDATION_ERROR" && error.hasField("token")));

/** POST /auth/invitations/preview → the screen state (never throws). */
async function previewInvitation(token: string): Promise<Preview> {
  try {
    const data = await authPost<InvitationPreviewWire>("/invitations/preview", {
      token,
    });
    return { state: "ready", data };
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

export function AcceptInvitationScreen() {
  const token = useFragmentToken();
  const passwordId = useId();
  const nameId = useId();
  const requirementsId = useId();
  const [preview, setPreview] = useState<Preview>({ state: "loading" });
  const [signedInAs, setSignedInAs] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [pending, setPending] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [accepted, setAccepted] = useState(false);
  const replacedTitle = useRef<HTMLHeadingElement>(null);
  const acceptedRef = useRef<HTMLDivElement>(null);
  const interacted = useRef(false);

  // One preview per page load (it has no side effects; "Try again" repeats it).
  useEffect(() => {
    if (!token) return;
    void previewInvitation(token).then(setPreview);
    readSession()
      .then((session) => setSignedInAs(session?.user.displayName ?? null))
      .catch(() => setSignedInAs(null));
  }, [token]);

  useEffect(() => {
    if (!interacted.current) return;
    if (accepted) acceptedRef.current?.focus();
    else if (preview.state === "unusable") replacedTitle.current?.focus();
  }, [accepted, preview.state]);

  const clearPasswords = () => {
    setPassword("");
    setConfirmation("");
  };

  const accept = async (account: "new" | "existing") => {
    if (pending || !token) return;
    interacted.current = true;
    setPending(true);
    setFeedback(null);
    setFieldErrors({});
    try {
      await authPost(
        "/invitations/accept",
        account === "new"
          ? { token, display_name: name.trim(), password }
          : { token },
      );
      clearPasswords();
      if (signedInAs === null) {
        assignLocation(LOGIN_AFTER_ACCEPT);
        return;
      }
      setPending(false);
      setAccepted(true);
    } catch (error) {
      clearPasswords();
      setPending(false);
      if (isUnusable(error)) {
        setPreview({ state: "unusable" });
        return;
      }
      if (error instanceof ApiError && error.code === "VALIDATION_ERROR") {
        const errors: Record<string, string> = {};
        if (error.hasField("display_name")) {
          errors.display_name = "Enter your name.";
        }
        if (error.hasField("password")) {
          errors.password = passwordFieldError(error.fieldCode("password"));
        }
        setFieldErrors(errors);
        document
          .getElementById(errors.display_name ? nameId : passwordId)
          ?.focus();
        return;
      }
      setFeedback(
        commonFeedback(error, (limited) =>
          tooManyRequests(limited, "reload this page"),
        ),
      );
    }
  };

  const submitNew = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void accept("new");
  };

  if (token === null) {
    return (
      <AuthenticationTemplate footer={BACK_TO_SIGN_IN}>
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
      <AuthenticationTemplate footer={BACK_TO_SIGN_IN}>
        <ErrorState
          titleAs="h1"
          titleRef={replacedTitle}
          title="This invitation can't be used"
          description="It may have expired, been withdrawn or already been accepted. Ask your institute administrator to send a new invitation."
        />
      </AuthenticationTemplate>
    );
  }

  if (preview.state === "failed") {
    return (
      <AuthenticationTemplate footer={BACK_TO_SIGN_IN}>
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
      <AuthenticationTemplate title="Accept your invitation">
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
        footer={BACK_TO_SIGN_IN}
      >
        <FeedbackRegion feedback={preview.feedback} />
      </AuthenticationTemplate>
    );
  }

  const {
    institute_name: institute,
    email_masked: email,
    account,
  } = preview.data;

  return (
    <AuthenticationTemplate
      title={`Join ${institute} on MTI 360`}
      description={`Invitation for ${email}`}
      notice={
        signedInAs !== null && !accepted ? (
          <Alert
            tone="info"
            title={`You're signed in as ${signedInAs}. Accepting this invitation doesn't change who is signed in.`}
          />
        ) : undefined
      }
      footer={accepted ? undefined : BACK_TO_SIGN_IN}
    >
      {accepted ? (
        <div
          ref={acceptedRef}
          tabIndex={-1}
          // a11y-focus: replaced content; receives programmatic focus only
          className="flex flex-col gap-4 outline-none"
        >
          <Alert
            tone="success"
            title={`Invitation accepted. You can now open ${institute}.`}
          />
          <div className="flex flex-col gap-2 tablet:flex-row">
            <Button onPress={() => assignLocation(AUTH_ROUTES.selectInstitute)}>
              Switch institute
            </Button>
            <Button
              variant="secondary"
              onPress={() => void signOut(LOGIN_AFTER_ACCEPT)}
            >
              Sign out
            </Button>
          </div>
        </div>
      ) : account === "existing" ? (
        <>
          <FeedbackRegion feedback={feedback} />
          <p className="text-body-sm text-text-primary">
            You already have an MTI 360 account for this email. Accept the
            invitation, then sign in with your current password.
          </p>
          <Button
            size="lg"
            fullWidth
            isPending={pending}
            onPress={() => void accept("existing")}
          >
            {pending ? "Accepting…" : "Accept invitation"}
          </Button>
        </>
      ) : (
        <>
          <PasswordRequirements id={requirementsId} />
          <FeedbackRegion feedback={feedback} />
          <Form
            aria-label="Create your account"
            validationErrors={fieldErrors}
            onSubmit={submitNew}
          >
            <RequiredLegend />
            <Input
              id={nameId}
              label="Your name"
              name="display_name"
              autoComplete="name"
              maxLength={200}
              isRequired
              isReadOnly={pending}
              value={name}
              onChange={setName}
              validate={(value) =>
                value && !value.trim() ? "Enter your name." : null
              }
              errorMessage={(validation) =>
                validation.validationDetails.valueMissing
                  ? "Enter your name."
                  : validation.validationErrors.join(" ")
              }
            />
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
                value && value !== password
                  ? "The passwords don't match."
                  : null
              }
              errorMessage={confirmPasswordError}
            />
            <Button type="submit" size="lg" fullWidth isPending={pending}>
              {pending ? "Creating account…" : "Create account and join"}
            </Button>
          </Form>
        </>
      )}
    </AuthenticationTemplate>
  );
}
