"use client";

import {
  useEffect,
  useId,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";

import {
  Alert,
  Button,
  Card,
  CardBody,
  CardHeader,
  Dialog,
  Form,
} from "@/design-system/components";
import { ApiError } from "@/lib/api/errors";
import type { MfaEnrolmentWire, RecoveryCodesWire } from "@/lib/api/types";
import { formFeedback, type FormFeedback } from "@/lib/authz/action-feedback";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { AuthenticatorSetupSteps } from "./AuthenticatorSetupSteps";
import { RequiredLegend } from "./components";
import { MfaCodeField } from "./MfaCodeField";
import {
  RecoveryCodesPanel,
  RECOVERY_CODES_TITLE,
  TENANT_RECOVERY_HINT,
} from "./RecoveryCodesPanel";

// Tenant AUTH-04 Sign-in security (T01-09C UI contract; D9B-9 completed):
// the signed-in member's own two-step verification on the existing T01-06
// tenant endpoints (ADR-0017 §6) — opt-in set-up and turning it off with a
// current authenticator code. Every call goes through the tenant session
// provider (`request`): the tenant cookie only (D9B-10), the CSRF token, and
// the T01-05 §11 matrix (401 → session ended; SESSION_REFRESH_REQUIRED →
// re-read, never resent). The server session is the only authority: the
// page re-reads it after every change and never decides MFA state itself.
//
// Set-up (D9C-2) starts ONLY on the explicit button press (each start
// replaces an unconfirmed secret; a StrictMode double effect would replace
// it silently). The secret and the otpauth:// URI live only in this
// component's state and are dropped on confirmation, cancel and unmount.
// Recovery codes are shown once (non-dismissable Dialog, required
// acknowledgement, beforeunload guard) and dropped on acknowledgement.
// The tenant realm has no recovery-code count, regeneration or step-up
// (T01-09C BG-T1, BG-T2): nothing here simulates them.

const INVALID_CODE =
  "That code didn't work. Check your authenticator app and try again.";
const MISSING_CODE = "Enter the 6-digit code from your authenticator app.";
const LOCKOUT_NOTE = "Each wrong code counts toward locking your account.";

type Flow =
  | { kind: "idle" }
  | { kind: "key"; enrolment: MfaEnrolmentWire }
  | { kind: "codes"; codes: string[] }
  | { kind: "remove" };

type Outcome = { tone: "success" | "info" | "warning"; title: string };

/** One term/description row: stacked on mobile, side by side from tablet. */
function Row({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1 tablet:flex-row tablet:gap-6">
      <dt className="text-text-secondary tablet:w-40 tablet:shrink-0">
        {term}
      </dt>
      <dd className="min-w-0 break-words text-text-primary">{children}</dd>
    </div>
  );
}

function FeedbackAlert({ feedback }: { feedback: FormFeedback | null }) {
  return (
    <div className="flex flex-col empty:hidden">
      {feedback && (
        <Alert tone={feedback.tone} title={feedback.title}>
          {feedback.body}
        </Alert>
      )}
    </div>
  );
}

/** A code form inside a Dialog (set-up confirmation and turning off). */
function CodeForm({
  formLabel,
  label,
  submitLabel,
  pendingLabel,
  destructive = false,
  onSubmit,
  onCancel,
}: {
  /** Accessible name of the form (distinct from the field's label). */
  formLabel: string;
  label: string;
  submitLabel: string;
  pendingLabel: string;
  destructive?: boolean;
  /** Resolves "invalid" for a refused code, otherwise anything. */
  onSubmit: (code: string) => Promise<"invalid" | FormFeedback | null>;
  onCancel: () => void;
}) {
  const fieldId = useId();
  const [code, setCode] = useState("");
  const [invalid, setInvalid] = useState(false);
  const [pending, setPending] = useState(false);
  const [feedback, setFeedback] = useState<FormFeedback | null>(null);
  const mounted = useRef(true);
  useEffect(
    () => () => {
      mounted.current = false;
    },
    [],
  );

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending) return;
    setPending(true);
    setInvalid(false);
    setFeedback(null);
    const value = code;
    setCode("");
    const outcome = await onSubmit(value.trim());
    if (!mounted.current) return;
    setPending(false);
    if (outcome === "invalid") setInvalid(true);
    else setFeedback(outcome);
    document.getElementById(fieldId)?.focus();
  };

  return (
    <Form aria-label={formLabel} onSubmit={(event) => void submit(event)}>
      <FeedbackAlert feedback={feedback} />
      <RequiredLegend />
      <MfaCodeField
        id={fieldId}
        label={label}
        description={LOCKOUT_NOTE}
        value={code}
        onChange={(value) => {
          setCode(value);
          setInvalid(false);
        }}
        invalid={invalid}
        invalidMessage={INVALID_CODE}
        missingMessage={MISSING_CODE}
      />
      <div className="flex flex-col-reverse gap-2 tablet:flex-row tablet:justify-end">
        <Button variant="secondary" isDisabled={pending} onPress={onCancel}>
          Cancel
        </Button>
        <Button
          type="submit"
          variant={destructive ? "destructive" : "primary"}
          isPending={pending}
        >
          {pending ? pendingLabel : submitLabel}
        </Button>
      </div>
    </Form>
  );
}

export function TenantSignInSecurity() {
  const { session, request, refresh } = useTenantSession();
  const accountHeading = useId();
  const mfaHeading = useId();
  const outcomeRef = useRef<HTMLDivElement>(null);
  const [flow, setFlow] = useState<Flow>({ kind: "idle" });
  const [starting, setStarting] = useState(false);
  const [feedback, setFeedback] = useState<FormFeedback | null>(null);
  const [outcome, setOutcome] = useState<Outcome | null>(null);

  // A finished change is announced and receives focus (the button that
  // opened the dialog is replaced by the new state's action).
  useEffect(() => {
    if (outcome) outcomeRef.current?.focus();
  }, [outcome]);

  const finish = (next: Outcome | null) => {
    setFlow({ kind: "idle" });
    setOutcome(next);
    void refresh().catch(() => undefined);
  };

  /** Errors of the provider's request: 401 navigates (null), 422 = code. */
  const failure = (error: unknown): "invalid" | FormFeedback | null => {
    if (error instanceof ApiError && error.code === "VALIDATION_ERROR") {
      return "invalid";
    }
    return formFeedback(error);
  };

  const start = async () => {
    if (starting) return;
    setStarting(true);
    setFeedback(null);
    setOutcome(null);
    try {
      const enrolment = await request<MfaEnrolmentWire>(
        "/session/mfa/enrolment",
        { method: "POST" },
      );
      setFlow({ kind: "key", enrolment });
    } catch (error) {
      if (error instanceof ApiError && error.code === "CONFLICT") {
        // Turned on elsewhere (another tab): show the server's state.
        setOutcome({
          tone: "info",
          title: "Two-step verification is already on.",
        });
        void refresh().catch(() => undefined);
      } else {
        setFeedback(formFeedback(error));
      }
    } finally {
      setStarting(false);
    }
  };

  const confirm = async (code: string) => {
    try {
      const confirmed = await request<RecoveryCodesWire>(
        "/session/mfa/enrolment/confirm",
        { method: "POST", body: { code } },
      );
      // Replacing the flow drops the secret and the URI from memory.
      setFlow({ kind: "codes", codes: confirmed.recovery_codes });
      return null;
    } catch (error) {
      return failure(error);
    }
  };

  const remove = async (code: string) => {
    try {
      await request<undefined>("/session/mfa/remove", {
        method: "POST",
        body: { code },
      });
      finish({ tone: "success", title: "Two-step verification is off." });
      return null;
    } catch (error) {
      return failure(error);
    }
  };

  const cancelSetup = () => {
    setFlow({ kind: "idle" });
    setOutcome({
      tone: "info",
      title:
        "Set-up cancelled. If you added an MTI 360 entry to your authenticator app, remove it.",
    });
  };

  return (
    <div className="flex flex-col gap-6">
      <Card as="section" aria-labelledby={accountHeading}>
        <CardHeader titleAs="h2" titleId={accountHeading} title="Account" />
        <CardBody>
          <dl className="flex flex-col gap-2">
            <Row term="Name">{session.user.displayName}</Row>
            <Row term="Email">
              <span className="break-all">{session.user.email}</span>
            </Row>
            {session.activeInstitute && (
              <Row term="Institute">{session.activeInstitute.name}</Row>
            )}
          </dl>
        </CardBody>
      </Card>

      <Card as="section" aria-labelledby={mfaHeading}>
        <CardHeader
          titleAs="h2"
          titleId={mfaHeading}
          title="Two-step verification"
          description="After your password, MTI 360 asks for a 6-digit code from an authenticator app on your phone or computer. It protects your account if your password is ever exposed."
        />
        <CardBody>
          <dl className="flex flex-col gap-2">
            <Row term="Status">
              {session.mfaEnabled ? "On — authenticator app" : "Off"}
            </Row>
            {session.mfaEnabled && (
              <Row term="Recovery codes">
                Saved when you turned it on. Each code works once.
              </Row>
            )}
          </dl>
          <div
            ref={outcomeRef}
            tabIndex={-1}
            // a11y-focus: outcome region; receives programmatic focus only
            className="flex flex-col outline-none empty:hidden"
          >
            {outcome && <Alert tone={outcome.tone} title={outcome.title} />}
          </div>
          <FeedbackAlert feedback={feedback} />
          <div>
            {session.mfaEnabled ? (
              <Button
                variant="secondary"
                onPress={() => {
                  setOutcome(null);
                  setFlow({ kind: "remove" });
                }}
              >
                Turn off two-step verification
              </Button>
            ) : (
              <Button isPending={starting} onPress={() => void start()}>
                {starting ? "Preparing…" : "Set up two-step verification"}
              </Button>
            )}
          </div>
        </CardBody>
      </Card>

      <Dialog
        isOpen={flow.kind === "key"}
        onOpenChange={(open) => {
          if (!open) cancelSetup();
        }}
        isDismissable={false}
        size="md"
        title="Add MTI 360 to your authenticator app"
        description="Then enter the code it shows to turn on two-step verification."
      >
        {flow.kind === "key" && (
          <div className="flex flex-col gap-4">
            <AuthenticatorSetupSteps
              secret={flow.enrolment.secret}
              uri={flow.enrolment.otpauth_uri}
            />
            <CodeForm
              formLabel="Turn on two-step verification"
              label="Code from your authenticator app"
              submitLabel="Verify and turn on"
              pendingLabel="Verifying…"
              onSubmit={confirm}
              onCancel={cancelSetup}
            />
          </div>
        )}
      </Dialog>

      <Dialog
        isOpen={flow.kind === "codes"}
        // The codes are shown once: only the acknowledgement closes this.
        onOpenChange={() => undefined}
        isDismissable={false}
        showCloseButton={false}
        size="md"
        title={RECOVERY_CODES_TITLE}
        description="Two-step verification is on. Keep these codes somewhere safe and separate from your authenticator app."
      >
        {flow.kind === "codes" && (
          <RecoveryCodesPanel
            codes={flow.codes}
            hint={TENANT_RECOVERY_HINT}
            continueLabel="Done"
            onContinue={() =>
              finish({ tone: "success", title: "Two-step verification is on." })
            }
          />
        )}
      </Dialog>

      <Dialog
        isOpen={flow.kind === "remove"}
        onOpenChange={(open) => {
          if (!open) setFlow({ kind: "idle" });
        }}
        isDismissable={false}
        size="sm"
        title="Turn off two-step verification?"
        description="You'll sign in with your password only, and your recovery codes stop working. Enter a current code from your authenticator app to confirm."
      >
        {flow.kind === "remove" && (
          <CodeForm
            formLabel="Turn off two-step verification"
            label="Authentication code"
            submitLabel="Turn off"
            pendingLabel="Turning off…"
            destructive
            onSubmit={remove}
            onCancel={() => setFlow({ kind: "idle" })}
          />
        )}
      </Dialog>
    </div>
  );
}
