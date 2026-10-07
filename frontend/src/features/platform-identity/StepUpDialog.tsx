"use client";

import { useId, useState, type FormEvent } from "react";

import { Alert, Button, Dialog, Form } from "@/design-system/components";
import { RequiredLegend } from "@/features/identity/components";
import { retryHint } from "@/features/identity/feedback";
import { MfaCodeField } from "@/features/identity/MfaCodeField";
import { apiRequest } from "@/lib/api/client";
import { ApiError, NetworkError } from "@/lib/api/errors";
import type { PlatformSessionWire } from "@/lib/api/types";
import { usePlatformSession } from "@/lib/session/PlatformSessionProvider";

// PAUTH-07 Step-up verification (T01-09B UI contract §9; D9B-6). Opened by
// PlatformSessionProvider when a platform API call answers 403
// STEP_UP_REQUIRED — reactively only; the browser clock decides nothing.
// TOTP only (the backend's step-up accepts no recovery code, BG-4). The code
// lives in this component's state and is cleared after every attempt.
//
// Success: the provider replaces the session from the response, closes the
// dialog (focus returns to where it was) and resends the original request
// exactly once. Cancel or Escape: nothing is performed and nothing is shown.
// 401 (expired, or the fifth wrong code revoked the session): session ended.
// SESSION_REFRESH_REQUIRED: the session is re-read (fresh CSRF token) and the
// dialog stays open; the code is never resent automatically.

type Notice = { tone: "error" | "warning"; title: string; body?: string };

const INVALID =
  "That code didn't work. Check your authenticator app and try again.";

export function StepUpDialog() {
  const {
    session,
    stepUpOpen,
    completeStepUp,
    cancelStepUp,
    handleUnauthorized,
    refresh,
  } = usePlatformSession();
  const codeId = useId();
  const [code, setCode] = useState("");
  const [invalid, setInvalid] = useState(false);
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);

  const reset = () => {
    setCode("");
    setInvalid(false);
    setPending(false);
    setNotice(null);
  };

  const cancel = () => {
    if (pending) return;
    reset();
    cancelStepUp();
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending) return;
    setPending(true);
    setInvalid(false);
    setNotice(null);
    try {
      const fresh = await apiRequest<PlatformSessionWire>(
        "/platform/session/step-up",
        {
          method: "POST",
          body: { code: code.trim() },
          csrfToken: session.csrfToken,
        },
      );
      reset();
      completeStepUp(fresh);
      return;
    } catch (error) {
      setCode("");
      setPending(false);
      if (error instanceof ApiError && error.status === 401) {
        // The session ended: navigate, and settle the waiting request as
        // not performed (it is never resent).
        reset();
        cancelStepUp();
        await handleUnauthorized();
        return;
      }
      if (error instanceof ApiError && error.code === "VALIDATION_ERROR") {
        setInvalid(true);
      } else if (
        error instanceof ApiError &&
        error.code === "SESSION_REFRESH_REQUIRED"
      ) {
        await refresh().catch(() => null);
        setNotice({
          tone: "warning",
          title: "Your session was refreshed. Try again.",
        });
      } else if (error instanceof ApiError && error.status === 429) {
        setNotice({
          tone: "warning",
          title: "Too many attempts",
          body: retryHint(error) ?? "Wait a few minutes before trying again.",
        });
      } else if (error instanceof NetworkError) {
        setNotice({
          tone: "error",
          title:
            "We couldn't reach MTI 360. Check your connection and try again.",
        });
      } else {
        setNotice({
          tone: "error",
          title: "Something went wrong on our side. Try again in a moment.",
        });
      }
      document.getElementById(codeId)?.focus();
    }
  };

  return (
    <Dialog
      isOpen={stepUpOpen}
      onOpenChange={(open) => {
        if (!open) cancel();
      }}
      isDismissable={false}
      size="sm"
      title="Confirm it's you"
      description="Enter the 6-digit code from your authenticator app to continue. Each wrong code counts toward locking your account."
    >
      <div className="flex flex-col gap-4">
        <div className="flex flex-col empty:hidden">
          {notice && (
            <Alert tone={notice.tone} title={notice.title}>
              {notice.body}
            </Alert>
          )}
        </div>
        <Form
          aria-label="Confirm it's you"
          onSubmit={(event) => void submit(event)}
        >
          <RequiredLegend />
          <MfaCodeField
            id={codeId}
            label="Authentication code"
            value={code}
            // The dialog opens on the person's action; the code field is its
            // only task (React Aria otherwise focuses the panel).
            // eslint-disable-next-line jsx-a11y/no-autofocus
            autoFocus
            onChange={(value) => {
              setCode(value);
              setInvalid(false);
            }}
            invalid={invalid}
            invalidMessage={INVALID}
            missingMessage="Enter the 6-digit code from your authenticator app."
          />
          <p className="text-body-sm text-text-secondary">
            Lost your authenticator? Ask another Super Admin to reset your
            two-step verification.
          </p>
          <div className="flex flex-col-reverse gap-2 tablet:flex-row tablet:justify-end">
            <Button variant="secondary" isDisabled={pending} onPress={cancel}>
              Cancel
            </Button>
            <Button type="submit" isPending={pending}>
              {pending ? "Verifying…" : "Verify and continue"}
            </Button>
          </div>
        </Form>
      </div>
    </Dialog>
  );
}
