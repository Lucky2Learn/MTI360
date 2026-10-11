"use client";

import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent } from "react";

import {
  Alert,
  Button,
  DatePicker,
  Form,
  IconButton,
  Input,
  Textarea,
} from "@/design-system/components";
import { AddIcon, DeleteIcon } from "@/design-system/icons";
import {
  FormActions,
  FormCell,
  FormGrid,
  FormSection,
} from "@/design-system/templates/FormLayout";
import type { FeeStructureWire, InvoiceDetailWire } from "@/lib/api/finance";
import type { FormFeedback } from "@/lib/authz/action-feedback";

import { focusFirstInvalid } from "../shared/forms";

import { invoicePath, NON_TAX_LABEL } from "./labels";
import { formatPaise, MAX_AMOUNT_MINOR, paiseInput, parsePaise } from "./money";
import { newIdempotencyKey, useFinanceMutation } from "./mutations";
import { istToday } from "./today";

// Issue a fee invoice, /app/finance/invoices/new (Phase 02-5; ADR-0022 §5,
// §7; readiness plan J2; addendum R3). The lines start from the course's
// active fee structure: a structure line keeps its fee head and may get
// another amount (zero drops it); lines can be added. Any difference from
// the structure needs a reason. Amounts are typed in rupees and sent as
// integer paise; the total shown is the exact sum of those integers. The
// server rebuilds the lines from the structure, decides whether they are
// adjusted, checks the due date (IST) and assigns the number. One
// idempotency key per form, reused on every retry, in the JSON body.

const LINES_MAX = 30;

type Line = {
  key: number;
  head: string;
  amount: string;
  /** The structure's amount in paise; null for a line added here. */
  structure: number | null;
};

type Errors = {
  due?: string;
  reason?: string;
  lines?: string;
  rows?: Record<number, { head?: string; amount?: string }>;
};

const AMOUNT_MESSAGE = "Enter an amount in rupees, e.g. 25000 or 1,25,000.50.";
const LINES_MESSAGE: Record<string, string> = {
  line_count: "Use between 1 and 30 fee heads.",
  duplicate_fee_head: "Use each fee head once.",
  amount_out_of_range: "Enter amounts up to ₹1,00,00,00,000.",
  total_out_of_range: "The total must be more than ₹0.",
};
const REASON_MESSAGE: Record<string, string> = {
  required: "Give the reason for changing the fee structure's amounts.",
  invalid: "Give a reason of up to 500 characters.",
  not_adjusted: "Remove the reason: the lines match the fee structure.",
};

let nextKey = 0;
const headKey = (head: string) =>
  head.trim().replace(/\s+/g, " ").toLowerCase();

function structureLines(structure: FeeStructureWire): Line[] {
  return structure.items.map((item) => ({
    key: nextKey++,
    head: item.fee_head,
    amount: paiseInput(item.amount_minor),
    structure: item.amount_minor,
  }));
}

/** UX only: whether the lines differ from the structure (the server decides). */
export function isAdjusted(lines: Line[]): boolean {
  return lines.some(
    (line) =>
      line.structure === null || parsePaise(line.amount) !== line.structure,
  );
}

export function validateIssue(
  values: { due: string | null; reason: string; lines: Line[] },
  today: string,
): Errors {
  const errors: Errors = {};
  if (!values.due) errors.due = "Choose the due date.";
  else if (values.due < today) errors.due = "Choose today or a later due date.";
  const rows: NonNullable<Errors["rows"]> = {};
  const heads = new Set<string>();
  let total = 0;
  values.lines.forEach((line, index) => {
    const row: { head?: string; amount?: string } = {};
    const head = headKey(line.head);
    if (line.structure === null) {
      if (!head || head.length > 100) {
        row.head = "Enter a fee head of up to 100 characters.";
      } else if (heads.has(head)) row.head = "Use each fee head once.";
    }
    heads.add(head);
    const amount = parsePaise(line.amount);
    if (amount === null) row.amount = AMOUNT_MESSAGE;
    else total += amount;
    if (row.head || row.amount) rows[index] = row;
  });
  if (Object.keys(rows).length > 0) errors.rows = rows;
  if (values.lines.length > LINES_MAX) errors.lines = LINES_MESSAGE.line_count;
  else if (!errors.rows && (total <= 0 || total > MAX_AMOUNT_MINOR)) {
    errors.lines = LINES_MESSAGE.total_out_of_range;
  }
  if (isAdjusted(values.lines) && !values.reason.trim()) {
    errors.reason = REASON_MESSAGE.required;
  }
  return errors;
}

export function InvoiceIssueForm({
  admission,
  structure,
  cancelHref,
}: {
  admission: { id: string; number: string };
  structure: FeeStructureWire;
  cancelHref: string;
}) {
  const router = useRouter();
  const mutate = useFinanceMutation("fee invoice");
  const formRef = useRef<HTMLDivElement>(null);
  const today = istToday();
  const [idempotencyKey] = useState(newIdempotencyKey);
  const [lines, setLines] = useState<Line[]>(() => structureLines(structure));
  const [due, setDue] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [errors, setErrors] = useState<Errors>({});
  const [feedback, setFeedback] = useState<FormFeedback | null>(null);
  const [pending, setPending] = useState(false);

  const adjusted = isAdjusted(lines);
  const allValid = lines.every((line) => parsePaise(line.amount) !== null);
  const total = lines.reduce(
    (sum, line) => sum + (parsePaise(line.amount) ?? 0),
    0,
  );

  const change = (index: number, patch: Partial<Line>) => {
    setLines((current) =>
      current.map((line, i) => (i === index ? { ...line, ...patch } : line)),
    );
    setErrors((current) => ({ ...current, rows: undefined, lines: undefined }));
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending) return;
    const found = validateIssue({ due, reason, lines }, today);
    setErrors(found);
    setFeedback(null);
    if (Object.keys(found).length > 0) {
      focusFirstInvalid(formRef.current);
      return;
    }
    setPending(true);
    const outcome = await mutate<InvoiceDetailWire>(
      "/invoices",
      {
        admission_id: admission.id,
        due_date: due,
        lines: lines.map((line) => ({
          fee_head: line.head.trim(),
          amount_minor: parsePaise(line.amount) as number,
        })),
        adjustment_reason: adjusted ? reason.trim() : null,
        idempotency_key: idempotencyKey,
      },
      null,
    );
    if (outcome.kind === "done") {
      router.push(invoicePath(outcome.data.id));
      return;
    }
    setPending(false);
    if (outcome.kind === "stale") return;
    if (outcome.kind === "feedback") {
      setFeedback(outcome.feedback);
      return;
    }
    const fields = outcome.fields;
    if (fields.admission_id === "live_invoice_exists") {
      setFeedback({
        tone: "warning",
        title: "This admission already has a fee invoice",
        body: "Cancel the current fee invoice to issue a new one. Reload the student's profile to see it.",
      });
      return;
    }
    if (fields.admission_id === "no_active_fee_structure") {
      setFeedback({
        tone: "warning",
        title: "The course has no active fee structure",
        body: "Activate a fee structure for this course, then issue the fee invoice.",
      });
      return;
    }
    if (fields.admission_id) {
      setFeedback({
        tone: "warning",
        title: "This admission isn't available",
        body: "Choose an admitted student of your campuses.",
      });
      return;
    }
    const mapped: Errors = {};
    if (fields.due_date) mapped.due = "Choose today or a later due date.";
    if (fields.adjustment_reason) {
      mapped.reason =
        REASON_MESSAGE[fields.adjustment_reason] ?? REASON_MESSAGE.invalid;
    }
    const lineCode = Object.entries(fields).find(([field]) =>
      field.startsWith("lines"),
    )?.[1];
    if (lineCode) {
      mapped.lines = LINES_MESSAGE[lineCode] ?? "Check the fee heads.";
    }
    if (Object.keys(mapped).length > 0) {
      setErrors(mapped);
      focusFirstInvalid(formRef.current);
      return;
    }
    setFeedback({ tone: "error", title: "The fee invoice wasn't issued" });
  };

  return (
    <div ref={formRef}>
      <Form
        aria-label="Issue fee invoice"
        validationBehavior="aria"
        onSubmit={(event) => void submit(event)}
      >
        {feedback && (
          <Alert tone={feedback.tone} title={feedback.title}>
            {feedback.body}
          </Alert>
        )}
        <FormSection
          title="Fee heads"
          description={`From ${structure.name}. Change an amount only for this student (zero leaves a fee head out); a change needs a reason. ${NON_TAX_LABEL}.`}
        >
          {errors.lines && (
            <Alert tone="error" title="Check the fee heads">
              {errors.lines}
            </Alert>
          )}
          <ul className="flex flex-col gap-4" aria-label="Fee heads">
            {lines.map((line, index) => (
              <li
                key={line.key}
                className="flex flex-col gap-3 tablet:flex-row tablet:items-start"
              >
                <div className="min-w-0 tablet:flex-1">
                  {line.structure === null ? (
                    <Input
                      label={`Fee head ${index + 1}`}
                      value={line.head}
                      onChange={(value) => change(index, { head: value })}
                      maxLength={100}
                      isRequired
                      isInvalid={Boolean(errors.rows?.[index]?.head)}
                      errorMessage={errors.rows?.[index]?.head}
                    />
                  ) : (
                    <div className="flex flex-col gap-1 tablet:pt-7">
                      <span className="text-body text-text-primary">
                        {line.head}
                      </span>
                      <span className="text-caption text-text-secondary">
                        {`Fee structure: ${formatPaise(line.structure)}`}
                      </span>
                    </div>
                  )}
                </div>
                <div className="tablet:w-48 tablet:shrink-0">
                  <Input
                    label={
                      line.structure === null
                        ? `Amount ${index + 1} (₹)`
                        : `Amount for ${line.head} (₹)`
                    }
                    value={line.amount}
                    onChange={(value) => change(index, { amount: value })}
                    inputMode="decimal"
                    maxLength={20}
                    isRequired
                    isInvalid={Boolean(errors.rows?.[index]?.amount)}
                    errorMessage={errors.rows?.[index]?.amount}
                  />
                </div>
                <div className="tablet:pt-7">
                  {line.structure === null && (
                    <IconButton
                      label={`Remove fee head ${index + 1}`}
                      icon={DeleteIcon}
                      variant="ghost"
                      onPress={() =>
                        setLines((current) =>
                          current.filter((_, i) => i !== index),
                        )
                      }
                    />
                  )}
                </div>
              </li>
            ))}
          </ul>
          <div className="flex flex-col gap-3 tablet:flex-row tablet:items-center tablet:justify-between">
            <Button
              variant="secondary"
              iconStart={AddIcon}
              isDisabled={lines.length >= LINES_MAX}
              onPress={() =>
                setLines((current) => [
                  ...current,
                  { key: nextKey++, head: "", amount: "", structure: null },
                ])
              }
            >
              Add fee head
            </Button>
            <p
              className="text-body font-medium text-text-primary"
              aria-live="polite"
            >
              <span className="text-text-secondary">Total </span>
              <span className="tabular-nums">
                {allValid ? formatPaise(total) : "—"}
              </span>
              {allValid && total !== structure.total_minor && (
                <span className="block text-caption font-normal text-text-secondary">
                  {`Fee structure total ${formatPaise(structure.total_minor)}`}
                </span>
              )}
            </p>
          </div>
        </FormSection>
        <FormSection title="Fee invoice">
          <FormGrid>
            <FormCell>
              <DatePicker
                label="Due date"
                value={due}
                minValue={today}
                onChange={(iso) => {
                  setDue(iso);
                  setErrors((current) => ({ ...current, due: undefined }));
                }}
                description="Overdue after this date (India Standard Time)."
                isRequired
                isInvalid={Boolean(errors.due)}
                errorMessage={errors.due}
              />
            </FormCell>
            <FormCell>
              <div className="flex flex-col gap-2">
                <span className="text-body-sm font-medium text-text-primary">
                  Admission
                </span>
                <span className="text-body text-text-primary">
                  {admission.number}
                </span>
              </div>
            </FormCell>
            {adjusted && (
              <FormCell span="full">
                <Textarea
                  label="Reason for the change"
                  value={reason}
                  onChange={(value) => {
                    setReason(value);
                    setErrors((current) => ({ ...current, reason: undefined }));
                  }}
                  description="For example: merit scholarship approved by the principal. Shown on the fee invoice."
                  rows={3}
                  maxLength={500}
                  showCount
                  isRequired
                  isInvalid={Boolean(errors.reason)}
                  errorMessage={errors.reason}
                />
              </FormCell>
            )}
          </FormGrid>
        </FormSection>
        <FormActions>
          <Button variant="secondary" href={cancelHref} isDisabled={pending}>
            Cancel
          </Button>
          <Button type="submit" isPending={pending}>
            Issue fee invoice
          </Button>
        </FormActions>
      </Form>
    </div>
  );
}
