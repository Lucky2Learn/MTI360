"use client";

import { useState } from "react";

import { Button, toast } from "@/design-system/components";
import type { InvoiceDetailWire, PaymentWire } from "@/lib/api/finance";
import { useTenantSession } from "@/lib/session/SessionProvider";

import {
  StatusTransitionDialog,
  type TransitionOutcome,
} from "../shared/StatusTransitionDialog";

import { paymentSummary } from "./InvoiceSections";
import {
  INVOICE_CANCEL,
  invoicePath,
  PAYMENT_RECORD,
  PAYMENT_STATUS_LABEL,
} from "./labels";
import { useFinanceMutation, newIdempotencyKey } from "./mutations";
import { RecordPaymentDialog } from "./RecordPaymentDialog";

// FIN-05 header actions (Phase 02-5; ADR-0022 §4, §8; readiness plan J3,
// J5). Record payment (payment.record) while something is left to collect;
// Cancel (invoice.cancel) while the fee invoice is live — the dialog names
// any pending or confirmed payment that must be resolved first, and the
// server refuses the cancellation until they are. Print for every reader.
// `openPayment` (Student 360's "Record payment") opens the payment dialog on
// arrival when recording is possible.
// Shown by permission for UX only; the API decides every action.

/** Payments that block cancellation: awaiting clearance or confirmed. */
export function openPayments(payments: PaymentWire[]): PaymentWire[] {
  return payments.filter(
    (payment) => payment.status === "PENDING" || payment.status === "CONFIRMED",
  );
}

function resolution(payments: PaymentWire[]): string {
  return payments
    .map(
      (payment) =>
        `${paymentSummary(payment)} (${PAYMENT_STATUS_LABEL[payment.status].toLowerCase()})`,
    )
    .join("; ");
}

const RESOLVE_HOW =
  "Fail or confirm each cheque or demand draft awaiting clearance, and have a colleague reverse each confirmed payment.";

export function InvoiceActions({
  invoice,
  openPayment = false,
}: {
  invoice: InvoiceDetailWire;
  openPayment?: boolean;
}) {
  const { can } = useTenantSession();
  const mutate = useFinanceMutation("fee invoice");
  const live = invoice.status !== "CANCELLED";
  const collectable = invoice.balance_minor - invoice.pending_minor;
  const canPay = live && collectable > 0 && can(PAYMENT_RECORD);
  const [dialog, setDialog] = useState<"pay" | "cancel" | null>(
    openPayment && canPay ? "pay" : null,
  );
  // One key per payment, kept across retries until a payment is recorded (R3).
  const [paymentKey, setPaymentKey] = useState(newIdempotencyKey);
  const close = (open: boolean) => !open && setDialog(null);
  const blocking = openPayments(invoice.payments);

  return (
    <>
      <Button variant="secondary" href={`${invoicePath(invoice.id)}/print`}>
        Print
      </Button>
      {live && can(INVOICE_CANCEL) && (
        <Button variant="secondary" onPress={() => setDialog("cancel")}>
          Cancel fee invoice
        </Button>
      )}
      {canPay && (
        <Button onPress={() => setDialog("pay")}>Record payment</Button>
      )}
      {dialog === "pay" && (
        <RecordPaymentDialog
          isOpen
          onOpenChange={close}
          invoice={invoice}
          collectableMinor={collectable}
          idempotencyKey={paymentKey}
          onRecorded={(payment) => {
            setPaymentKey(newIdempotencyKey());
            if (payment.status === "PENDING") {
              toast.success(
                `${payment.method === "CHEQUE" ? "Cheque" : "Demand draft"} recorded — awaiting clearance`,
              );
            } else {
              toast.success(
                payment.receipt
                  ? `Payment recorded — receipt ${payment.receipt.number}`
                  : "Payment recorded",
              );
            }
          }}
        />
      )}
      {dialog === "cancel" && (
        <StatusTransitionDialog
          isOpen
          onOpenChange={close}
          title={`Cancel ${invoice.number}?`}
          description={
            blocking.length > 0
              ? `Resolve these payments first: ${resolution(blocking)}. ${RESOLVE_HOW}`
              : "A cancelled fee invoice stays in the history and can't be paid. A new fee invoice for this admission gets a new number."
          }
          choices={[
            {
              value: "CANCELLED",
              label: "Cancelled",
              requiresReason: true,
              requiresTarget: false,
            },
          ]}
          initialTarget="CANCELLED"
          onSubmit={async ({ reason }): Promise<TransitionOutcome> => {
            const outcome = await mutate(
              `/invoices/${invoice.id}/cancel`,
              { reason, version: invoice.version },
              `${invoice.number} cancelled`,
            );
            if (outcome.kind === "done" || outcome.kind === "stale") {
              return { kind: "done" };
            }
            if (outcome.kind === "feedback") return outcome;
            if (outcome.fields.status === "open_payments") {
              return {
                kind: "feedback",
                feedback: {
                  tone: "warning",
                  title: "Resolve the payments first",
                  body:
                    blocking.length > 0
                      ? `${resolution(blocking)}. ${RESOLVE_HOW}`
                      : `${RESOLVE_HOW} Reload the page to see the latest payments.`,
                },
              };
            }
            if (outcome.fields.status === "invalid_transition") {
              return {
                kind: "feedback",
                feedback: {
                  tone: "warning",
                  title: "This fee invoice is already cancelled",
                  body: "Reload the page to see its current status.",
                },
              };
            }
            if (outcome.fields.reason) {
              return {
                kind: "fields",
                fields: { reason: "Enter a reason of up to 500 characters." },
              };
            }
            return {
              kind: "feedback",
              feedback: {
                tone: "error",
                title: "The fee invoice wasn't cancelled",
              },
            };
          }}
        />
      )}
    </>
  );
}
