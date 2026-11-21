"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { AlertDialog, Button, toast } from "@/design-system/components";
import {
  ReasonDialog,
  type ReasonOutcome,
} from "@/features/finance/ReasonDialog";
import {
  ApiError,
  StepUpCancelledError,
  StepUpFailedError,
} from "@/lib/api/errors";
import type { TenantDetailWire } from "@/lib/api/platform-tenants";
import { formFeedback, notifyActionError } from "@/lib/authz/action-feedback";
import { usePlatformSession } from "@/lib/session/PlatformSessionProvider";

import {
  SUSPENDABLE,
  TENANT_CREATE,
  TENANT_REACTIVATE,
  TENANT_SUSPEND,
} from "./labels";

// PLAT-05 tenant actions (T01-07 API; D15, D7-6, D7-8). Suspend and
// reactivate need a reason and send the loaded version; the API asks for a
// fresh authenticator code (403 STEP_UP_REQUIRED), which the platform session
// provider handles with PAUTH-07 and one resend. Resending the owner
// invitation revokes the previous link; the API accepts it (202) and emails
// after the response, so the UI says the email is being sent, never that it
// arrived. Buttons follow the session's permissions and the tenant's status
// (UX only); the API authorizes and validates every request again, and
// nothing changes on screen until it answers.

type Transition = "suspend" | "reactivate";

const NOT_CONFIRMED = {
  tone: "error",
  title: "We couldn't confirm it's you. Try again.",
} as const;

function transitionError(error: unknown, action: Transition): ReasonOutcome {
  const verb = action === "suspend" ? "suspended" : "reactivated";
  if (error instanceof StepUpCancelledError) {
    return {
      kind: "feedback",
      feedback: {
        tone: "warning",
        title: `The institute wasn't ${verb}`,
        body: "Confirm it's you with your authenticator code to continue.",
      },
    };
  }
  if (error instanceof StepUpFailedError) {
    return { kind: "feedback", feedback: NOT_CONFIRMED };
  }
  if (error instanceof ApiError && error.code === "VALIDATION_ERROR") {
    return {
      kind: "reason",
      message: "Enter a reason of up to 500 characters.",
    };
  }
  if (error instanceof ApiError && error.code === "CONFLICT") {
    return {
      kind: "feedback",
      feedback: {
        tone: "warning",
        title: `The institute wasn't ${verb}`,
        body: "It changed since this page was loaded. Its current status is shown now; check it before trying again.",
      },
    };
  }
  const feedback = formFeedback(error);
  // 401 (the provider navigates) and 404 (the page re-reads) close quietly.
  return feedback ? { kind: "feedback", feedback } : { kind: "done" };
}

export function TenantLifecycleActions({
  tenant,
}: {
  tenant: TenantDetailWire;
}) {
  const router = useRouter();
  const { can, request } = usePlatformSession();
  const [dialog, setDialog] = useState<Transition | null>(null);
  const suspendable = SUSPENDABLE.has(tenant.status) && can(TENANT_SUSPEND);
  const reactivatable = tenant.status === "SUSPENDED" && can(TENANT_REACTIVATE);

  const run = async (
    action: Transition,
    reason: string,
  ): Promise<ReasonOutcome> => {
    try {
      await request<TenantDetailWire>(`/tenants/${tenant.id}/${action}`, {
        method: "POST",
        body: { reason, version: tenant.version },
      });
    } catch (error) {
      const outcome = transitionError(error, action);
      if (
        error instanceof ApiError &&
        (error.code === "CONFLICT" || error.code === "NOT_FOUND")
      ) {
        router.refresh();
      }
      return outcome;
    }
    toast.success(
      action === "suspend"
        ? `${tenant.name} is suspended`
        : `${tenant.name} is active again`,
    );
    router.refresh();
    return { kind: "done" };
  };

  if (!suspendable && !reactivatable) return null;
  const close = (open: boolean) => !open && setDialog(null);
  return (
    <>
      {suspendable && (
        <Button variant="secondary" onPress={() => setDialog("suspend")}>
          Suspend tenant
        </Button>
      )}
      {reactivatable && (
        <Button onPress={() => setDialog("reactivate")}>
          Reactivate tenant
        </Button>
      )}
      {dialog === "suspend" && (
        <ReasonDialog
          isOpen
          onOpenChange={close}
          title={`Suspend ${tenant.name}?`}
          description="Everyone signed in to this institute is signed out at once. Staff and students can't sign in, and its public website is offline, until it is reactivated. You may be asked for your authenticator code."
          reasonLabel="Reason"
          reasonDescription="Recorded in the audit log."
          confirmLabel="Suspend tenant"
          onSubmit={(reason) => run("suspend", reason)}
        />
      )}
      {dialog === "reactivate" && (
        <ReasonDialog
          isOpen
          onOpenChange={close}
          title={`Reactivate ${tenant.name}?`}
          description="The institute becomes active. Staff and students can sign in again; sessions ended by the suspension stay ended. You may be asked for your authenticator code."
          reasonLabel="Reason"
          reasonDescription="Recorded in the audit log."
          confirmLabel="Reactivate tenant"
          onSubmit={(reason) => run("reactivate", reason)}
        />
      )}
    </>
  );
}

/** Offered while the administrator has not joined (D7-8). */
export function ResendInvitationAction({
  tenant,
}: {
  tenant: TenantDetailWire;
}) {
  const router = useRouter();
  const { can, request } = usePlatformSession();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const owner = tenant.owner;
  if (owner?.status !== "INVITED" || !can(TENANT_CREATE)) return null;

  const resend = async () => {
    setPending(true);
    try {
      await request<void>(`/tenants/${tenant.id}/owner-invitation/resend`, {
        method: "POST",
      });
      toast.success("A new invitation was issued", {
        description: `It is being emailed to ${owner.email}. The previous invitation link no longer works.`,
      });
    } catch (error) {
      if (error instanceof ApiError && error.code === "CONFLICT") {
        toast.warning("The invitation wasn't resent", {
          description:
            "The administrator may have joined already, or their account is disabled. The latest details are shown now.",
        });
        router.refresh();
      } else if (error instanceof ApiError && error.code === "NOT_FOUND") {
        router.refresh();
      } else {
        notifyActionError(error, "tenant-invitation-resend");
      }
    } finally {
      setPending(false);
      setOpen(false);
    }
  };

  return (
    <>
      <Button variant="secondary" size="sm" onPress={() => setOpen(true)}>
        Resend invitation
      </Button>
      <AlertDialog
        isOpen={open}
        onOpenChange={setOpen}
        title="Send a new invitation?"
        description={`A new invitation is emailed to ${owner.email}. The previous invitation link stops working.`}
        confirmLabel="Send new invitation"
        isPending={pending}
        onConfirm={() => void resend()}
      />
    </>
  );
}
