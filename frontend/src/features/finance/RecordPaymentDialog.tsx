"use client";

import { useRef, useState, type FormEvent } from "react";

import {
  Alert,
  Button,
  DatePicker,
  Dialog,
  Form,
  Input,
  Select,
} from "@/design-system/components";
import type {
  InvoiceWire,
  PaymentMethod,
  PaymentWire,
} from "@/lib/api/finance";
import type { FormFeedback } from "@/lib/authz/action-feedback";

import { focusFirstInvalid } from "../shared/forms";

import { CLEARANCE_METHODS, METHOD_LABEL, REFERENCE_LABEL } from "./labels";
import { formatPaise, parsePaise } from "./money";
import { useFinanceMutation } from "./mutations";
import { istToday } from "./today";

// FIN-05 Record payment (Phase 02-5; ADR-0022 §4; addendum R3). An offline
// payment against one fee invoice: cash, UPI and bank transfer are confirmed
// on save (balance and receipt at once); a cheque or demand draft is saved
// awaiting clearance and changes nothing until confirmed. The amount is typed
// in rupees and sent as integer paise. The idempotency key is the caller's —
// created once per payment and kept across retries until one succeeds — and
// travels in the JSON body. The server re-checks the amount against the
// balance (pending cheques included), the reference and the date.

export type RecordPaymentDialogProps = {
  invoice: Pick<InvoiceWire, "id" | "number" | "student">;
  /** The balance less cheques and drafts awaiting clearance (server values). */
  collectableMinor: number;
  idempotencyKey: string;
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  onRecorded: (payment: PaymentWire) => void;
};

const METHODS: PaymentMethod[] = [
  "CASH",
  "UPI",
  "BANK_TRANSFER",
  "CHEQUE",
  "DEMAND_DRAFT",
];

type Field = "amount" | "method" | "reference" | "received";
type Errors = Partial<Record<Field, string>>;

const AMOUNT_MESSAGE = "Enter an amount in rupees, e.g. 25000 or 1,25,000.50.";

const SERVER_FIELDS: Record<string, Record<string, [Field, string]>> = {
  amount_minor: {
    exceeds_balance: [
      "amount",
      "The amount is more than the balance still to collect (cheques and drafts awaiting clearance included).",
    ],
  },
  reference: {
    required: ["reference", "Enter the reference for this payment method."],
    invalid: ["reference", "Use up to 100 characters."],
  },
  received_on: {
    in_the_future: ["received", "Enter the date the money was received."],
  },
};

export function RecordPaymentDialog({
  invoice,
  collectableMinor,
  idempotencyKey,
  isOpen,
  onOpenChange,
  onRecorded,
}: RecordPaymentDialogProps) {
  return (
    <Dialog
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      title={`Record a payment for ${invoice.number}`}
      description={`${invoice.student.full_name} · ${invoice.student.number}. Up to ${formatPaise(collectableMinor)} can be recorded.`}
      size="md"
    >
      {(close) => (
        <PaymentForm
          invoice={invoice}
          collectableMinor={collectableMinor}
          idempotencyKey={idempotencyKey}
          onCancel={close}
          onRecorded={(payment) => {
            onRecorded(payment);
            close();
          }}
        />
      )}
    </Dialog>
  );
}

function PaymentForm({
  invoice,
  collectableMinor,
  idempotencyKey,
  onCancel,
  onRecorded,
}: {
  invoice: RecordPaymentDialogProps["invoice"];
  collectableMinor: number;
  idempotencyKey: string;
  onCancel: () => void;
  onRecorded: (payment: PaymentWire) => void;
}) {
  const mutate = useFinanceMutation("fee invoice");
  const formRef = useRef<HTMLDivElement>(null);
  const today = istToday();
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState<PaymentMethod | null>(null);
  const [reference, setReference] = useState("");
  const [received, setReceived] = useState<string | null>(today);
  const [errors, setErrors] = useState<Errors>({});
  const [feedback, setFeedback] = useState<FormFeedback | null>(null);
  const [pending, setPending] = useState(false);
  const clearance = method !== null && CLEARANCE_METHODS.has(method);

  const clear = (field: Field) =>
    setErrors((current) => ({ ...current, [field]: undefined }));

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending) return;
    const paise = parsePaise(amount);
    const next: Errors = {};
    if (paise === null || paise <= 0) next.amount = AMOUNT_MESSAGE;
    else if (paise > collectableMinor) {
      next.amount = `Enter at most ${formatPaise(collectableMinor)}, the balance still to collect.`;
    }
    if (!method) next.method = "Choose how the money was paid.";
    else if (method !== "CASH" && !reference.trim()) {
      next.reference = "Enter the reference for this payment method.";
    }
    if (!received) next.received = "Enter the date the money was received.";
    else if (received > today) {
      next.received = "Enter the date the money was received.";
    }
    setErrors(next);
    setFeedback(null);
    if (Object.keys(next).length > 0 || paise === null || !method) {
      focusFirstInvalid(formRef.current);
      return;
    }
    setPending(true);
    const outcome = await mutate<PaymentWire>(
      `/invoices/${invoice.id}/payments`,
      {
        amount_minor: paise,
        method,
        reference: reference.trim() || null,
        received_on: received,
        idempotency_key: idempotencyKey,
      },
      null,
    );
    setPending(false);
    if (outcome.kind === "done") {
      onRecorded(outcome.data);
    } else if (outcome.kind === "stale") {
      onCancel();
    } else if (outcome.kind === "feedback") {
      setFeedback(outcome.feedback);
    } else if (outcome.fields.status === "invoice_cancelled") {
      setFeedback({
        tone: "warning",
        title: "This fee invoice is cancelled",
        body: "Payments can't be recorded against a cancelled fee invoice.",
      });
    } else {
      const mapped: Errors = {};
      for (const [field, code] of Object.entries(outcome.fields)) {
        const known = SERVER_FIELDS[field]?.[code];
        if (known) mapped[known[0]] = known[1];
      }
      if (Object.keys(mapped).length > 0) {
        setErrors(mapped);
        focusFirstInvalid(formRef.current);
      } else {
        setFeedback({ tone: "error", title: "The payment wasn't recorded" });
      }
    }
  };

  return (
    <div ref={formRef}>
      <Form
        aria-label="Record payment"
        validationBehavior="aria"
        onSubmit={(event) => void submit(event)}
      >
        {feedback && (
          <Alert tone={feedback.tone} title={feedback.title}>
            {feedback.body}
          </Alert>
        )}
        <Input
          label="Amount (₹)"
          value={amount}
          onChange={(value) => {
            setAmount(value);
            clear("amount");
          }}
          inputMode="decimal"
          maxLength={20}
          isRequired
          isInvalid={Boolean(errors.amount)}
          errorMessage={errors.amount}
        />
        <Select
          label="Payment method"
          options={METHODS.map((value) => ({
            id: value,
            label: METHOD_LABEL[value],
          }))}
          value={method}
          onChange={(value) => {
            setMethod(value as PaymentMethod | null);
            clear("method");
            clear("reference");
          }}
          isRequired
          isInvalid={Boolean(errors.method)}
          errorMessage={errors.method}
        />
        {clearance && (
          <Alert tone="info" title="Saved as awaiting clearance">
            The balance and the receipt change only when the{" "}
            {method === "CHEQUE" ? "cheque" : "demand draft"} is confirmed as
            cleared.
          </Alert>
        )}
        <Input
          label={method ? REFERENCE_LABEL[method] : "Reference"}
          value={reference}
          onChange={(value) => {
            setReference(value);
            clear("reference");
          }}
          maxLength={100}
          isRequired={method !== null && method !== "CASH"}
          isInvalid={Boolean(errors.reference)}
          errorMessage={errors.reference}
        />
        <DatePicker
          label="Received on"
          value={received}
          maxValue={today}
          onChange={(iso) => {
            setReceived(iso);
            clear("received");
          }}
          isRequired
          isInvalid={Boolean(errors.received)}
          errorMessage={errors.received}
        />
        <div className="flex flex-col-reverse gap-2 pt-2 tablet:flex-row tablet:justify-end">
          <Button variant="secondary" onPress={onCancel} isDisabled={pending}>
            Cancel
          </Button>
          <Button type="submit" isPending={pending}>
            Record payment
          </Button>
        </div>
      </Form>
    </div>
  );
}
