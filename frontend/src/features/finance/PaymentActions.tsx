"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { AlertDialog, Button, toast } from "@/design-system/components";
import type { PaymentWire } from "@/lib/api/finance";
import { useTenantSession } from "@/lib/session/SessionProvider";

import {
  METHOD_LABEL,
  PAYMENT_RECORD,
  PAYMENT_REVERSE,
  receiptPath,
} from "./labels";
import { formatPaise } from "./money";
import { useFinanceMutation, type FinanceOutcome } from "./mutations";
import { ReasonDialog, type ReasonOutcome } from "./ReasonDialog";

// FIN-07 payment actions (Phase 02-5; ADR-0022 §4, §9; addendum R1). A cheque
// or demand draft awaiting clearance is confirmed (receipt, balance) or
// failed with a reason by a holder of payment.record. A confirmed payment is
// reversed with a reason by a holder of payment.reverse who did not record
// it: `recorded_by_me` hides Reverse for its recorder, and the server refuses
// the recorder regardless (422 recorder_cannot_reverse). Every action sends
// the loaded version; the server's answer wins.

const SAME_PERSON =
  "You recorded this payment. A payment is reversed by someone other than the person who recorded it — ask a colleague with reversal access.";

function reasonOutcome(
  outcome: FinanceOutcome,
  action: "fail" | "reverse",
): ReasonOutcome {
  if (outcome.kind === "done" || outcome.kind === "stale") {
    return { kind: "done" };
  }
  if (outcome.kind === "feedback") return outcome;
  if (outcome.fields.payment === "recorder_cannot_reverse") {
    return {
      kind: "feedback",
      feedback: {
        tone: "warning",
        title: "You can't reverse your own payment",
        body: SAME_PERSON,
      },
    };
  }
  if (outcome.fields.status === "invalid_transition") {
    return {
      kind: "feedback",
      feedback: {
        tone: "warning",
        title:
          action === "fail"
            ? "This payment is no longer awaiting clearance"
            : "This payment is no longer confirmed",
        body: "Reload the page to see its current status.",
      },
    };
  }
  if (outcome.fields.reason) {
    return {
      kind: "reason",
      message: "Enter a reason of up to 500 characters.",
    };
  }
  return {
    kind: "feedback",
    feedback: {
      tone: "error",
      title:
        action === "fail"
          ? "The payment wasn't marked as failed"
          : "The payment wasn't reversed",
    },
  };
}

/** Why Reverse is not offered to the recorder (UX only; the server enforces). */
export function RecorderNotice({ payment }: { payment: PaymentWire }) {
  const { can } = useTenantSession();
  if (
    payment.status !== "CONFIRMED" ||
    !payment.recorded_by_me ||
    !can(PAYMENT_REVERSE)
  ) {
    return null;
  }
  return <p className="text-body-sm text-text-secondary">{SAME_PERSON}</p>;
}

export function PaymentActions({ payment }: { payment: PaymentWire }) {
  const router = useRouter();
  const { can } = useTenantSession();
  const mutate = useFinanceMutation("payment");
  const [dialog, setDialog] = useState<"confirm" | "fail" | "reverse" | null>(
    null,
  );
  const [pending, setPending] = useState(false);
  const close = (open: boolean) => !open && setDialog(null);
  const what = `${METHOD_LABEL[payment.method].toLowerCase()} of ${formatPaise(payment.amount_minor)}`;
  const awaiting = payment.status === "PENDING" && can(PAYMENT_RECORD);
  const reversible =
    payment.status === "CONFIRMED" &&
    !payment.recorded_by_me &&
    can(PAYMENT_REVERSE);

  const confirm = async () => {
    setPending(true);
    const outcome = await mutate<PaymentWire>(
      `/payments/${payment.id}/confirm`,
      { version: payment.version },
      null,
    );
    setPending(false);
    setDialog(null);
    if (outcome.kind === "done") {
      toast.success(
        outcome.data.receipt
          ? `Payment confirmed — receipt ${outcome.data.receipt.number}`
          : "Payment confirmed",
      );
    } else if (outcome.kind === "fields") {
      if (outcome.fields.amount_minor === "exceeds_balance") {
        toast.error(
          "Confirming this payment would collect more than the fee invoice's total. Reverse or fail another payment first.",
        );
      } else {
        toast.warning(
          "This payment is no longer awaiting clearance. The latest status is shown.",
        );
        router.refresh();
      }
    } else if (outcome.kind === "feedback") {
      toast.error(outcome.feedback.title, {
        description: outcome.feedback.body,
      });
    }
  };

  return (
    <>
      {payment.receipt && (
        <Button variant="secondary" href={receiptPath(payment.id)}>
          {payment.receipt.cancelled
            ? "View cancelled receipt"
            : "View receipt"}
        </Button>
      )}
      {awaiting && (
        <>
          <Button variant="secondary" onPress={() => setDialog("fail")}>
            Mark as failed
          </Button>
          <Button onPress={() => setDialog("confirm")}>
            Confirm clearance
          </Button>
        </>
      )}
      {reversible && (
        <Button variant="secondary" onPress={() => setDialog("reverse")}>
          Reverse payment
        </Button>
      )}
      <AlertDialog
        isOpen={dialog === "confirm"}
        onOpenChange={close}
        title={`Confirm the ${what} as cleared?`}
        description={`A receipt is issued and the fee invoice ${payment.invoice.number} balance drops by ${formatPaise(payment.amount_minor)}. Confirm only once the bank has credited the money.`}
        confirmLabel="Confirm clearance"
        isPending={pending}
        onConfirm={() => void confirm()}
      />
      {dialog === "fail" && (
        <ReasonDialog
          isOpen
          onOpenChange={close}
          title={`Mark the ${what} as failed?`}
          description="Use this when the cheque or demand draft was not honoured. No receipt is issued and the balance doesn't change."
          reasonLabel="Reason"
          reasonDescription="For example: cheque returned — insufficient funds."
          confirmLabel="Mark as failed"
          onSubmit={async (reason) =>
            reasonOutcome(
              await mutate(
                `/payments/${payment.id}/fail`,
                { reason, version: payment.version },
                "Payment marked as failed",
              ),
              "fail",
            )
          }
        />
      )}
      {dialog === "reverse" && (
        <ReasonDialog
          isOpen
          onOpenChange={close}
          title={`Reverse the ${what}?`}
          description={`The fee invoice ${payment.invoice.number} balance goes back up by ${formatPaise(payment.amount_minor)}. The receipt${payment.receipt ? ` ${payment.receipt.number}` : ""} stays on record, shown as cancelled. Nothing is deleted.`}
          reasonLabel="Reason for the reversal"
          reasonDescription="For example: recorded against the wrong student."
          confirmLabel="Reverse payment"
          onSubmit={async (reason) =>
            reasonOutcome(
              await mutate(
                `/payments/${payment.id}/reverse`,
                { reason, version: payment.version },
                "Payment reversed",
              ),
              "reverse",
            )
          }
        />
      )}
    </>
  );
}
