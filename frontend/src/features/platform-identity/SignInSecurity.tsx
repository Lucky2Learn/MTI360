"use client";

import { useId, useState, type ReactNode } from "react";

import {
  Alert,
  AlertDialog,
  Button,
  Card,
  CardBody,
  CardHeader,
  Dialog,
} from "@/design-system/components";
import {
  ApiError,
  StepUpCancelledError,
  StepUpFailedError,
} from "@/lib/api/errors";
import type { RecoveryCodesWire } from "@/lib/api/types";
import { formFeedback, type FormFeedback } from "@/lib/authz/action-feedback";
import { PLATFORM_PROFILE } from "@/lib/session/platform-routes";
import {
  lowRecoveryCodes,
  platformRoleLabel,
  type PlatformSession,
} from "@/lib/session/platform-session";
import { usePlatformSession } from "@/lib/session/PlatformSessionProvider";

import { RecoveryCodesPanel, RECOVERY_CODES_TITLE } from "./RecoveryCodesPanel";

// Partial PLAT-52 Sign-in security (T01-09B UI contract §10; D9B-8 accepted):
// identity (read-only), two-step verification status, recovery codes
// remaining and "Generate new recovery codes" — the only step-up action of
// T01-09B. Everything comes from the server session; nothing here decides
// access. The rest of PLAT-52 is Phase 02 (T02-23).
//
// Generate: AlertDialog (old codes stop working) → POST
// /platform/session/mfa/recovery-codes through the session provider, which
// opens PAUTH-07 on 403 STEP_UP_REQUIRED and resends once → the new codes in
// a non-dismissable Dialog (PAUTH-05) → acknowledgement drops them and
// re-reads the session (the remaining count).

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

function remainingText(session: PlatformSession): string {
  const remaining = session.mfa.recoveryCodesRemaining ?? 0;
  return remaining === 1 ? "1 code left" : `${remaining} codes left`;
}

/** D9B-7: shown on Overview and Sign-in security when ≤ 3 codes remain. */
export function LowRecoveryCodesAlert({ withAction }: { withAction: boolean }) {
  const { session } = usePlatformSession();
  if (!lowRecoveryCodes(session)) return null;
  const none = (session.mfa.recoveryCodesRemaining ?? 0) === 0;
  return (
    <Alert
      tone="warning"
      title={
        none
          ? "You have no recovery codes left"
          : `You're running low on recovery codes (${remainingText(session)})`
      }
      action={
        withAction ? (
          <Button variant="secondary" size="sm" href={PLATFORM_PROFILE}>
            Generate new codes
          </Button>
        ) : undefined
      }
    >
      Generate new codes so you can still sign in if you can&apos;t use your
      authenticator app.
    </Alert>
  );
}

export function SignInSecurity() {
  const { session, request, refresh } = usePlatformSession();
  const accountHeading = useId();
  const mfaHeading = useId();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [codes, setCodes] = useState<string[] | null>(null);
  const [feedback, setFeedback] = useState<FormFeedback | null>(null);

  const generate = async () => {
    setPending(true);
    setFeedback(null);
    try {
      const fresh = await request<RecoveryCodesWire>(
        "/session/mfa/recovery-codes",
        {
          method: "POST",
        },
      );
      setCodes(fresh.recovery_codes);
    } catch (error) {
      if (error instanceof StepUpCancelledError) return;
      if (error instanceof StepUpFailedError) {
        setFeedback({
          tone: "error",
          title: "We couldn't confirm it's you. Try again.",
        });
        return;
      }
      if (error instanceof ApiError && error.code === "CONFLICT") {
        setFeedback({
          tone: "warning",
          title: "Two-step verification isn't set up on this account.",
        });
        return;
      }
      setFeedback(formFeedback(error));
    } finally {
      setPending(false);
    }
  };

  const acknowledge = () => {
    setCodes(null);
    void refresh().catch(() => undefined);
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
            <Row term="Roles">
              {session.roles.length > 0
                ? session.roles.map(platformRoleLabel).join(", ")
                : "No role assigned"}
            </Row>
          </dl>
        </CardBody>
      </Card>

      <Card as="section" aria-labelledby={mfaHeading}>
        <CardHeader
          titleAs="h2"
          titleId={mfaHeading}
          title="Two-step verification"
          description="Required for platform administration. Your authenticator app is asked for at every sign-in and before sensitive actions."
        />
        <CardBody>
          <dl className="flex flex-col gap-2">
            <Row term="Status">
              {session.mfa.enrolled ? "On — authenticator app" : "Not set up"}
            </Row>
            <Row term="Recovery codes">{remainingText(session)}</Row>
          </dl>
          <LowRecoveryCodesAlert withAction={false} />
          <div className="flex flex-col empty:hidden">
            {feedback && (
              <Alert tone={feedback.tone} title={feedback.title}>
                {feedback.body}
              </Alert>
            )}
          </div>
          <div>
            <Button
              variant="secondary"
              isPending={pending}
              isDisabled={!session.mfa.enrolled}
              onPress={() => setConfirmOpen(true)}
            >
              {pending ? "Generating…" : "Generate new recovery codes"}
            </Button>
          </div>
        </CardBody>
      </Card>

      <AlertDialog
        isOpen={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Generate new recovery codes?"
        description="Your current recovery codes stop working as soon as new ones are generated. You may be asked for your authenticator code."
        confirmLabel="Generate new codes"
        onConfirm={() => {
          setConfirmOpen(false);
          void generate();
        }}
      />

      <Dialog
        isOpen={codes !== null}
        // The codes are shown once: only the acknowledgement closes this.
        onOpenChange={() => undefined}
        isDismissable={false}
        showCloseButton={false}
        size="md"
        title={RECOVERY_CODES_TITLE}
        description="Your previous recovery codes no longer work."
      >
        {codes && (
          <RecoveryCodesPanel
            codes={codes}
            onContinue={acknowledge}
            continueLabel="Done"
          />
        )}
      </Dialog>
    </div>
  );
}
