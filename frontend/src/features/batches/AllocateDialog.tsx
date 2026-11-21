"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import {
  Alert,
  Button,
  Dialog,
  EmptyState,
  Form,
  RadioGroup,
  Search,
  SkeletonText,
  Textarea,
} from "@/design-system/components";
import type {
  AllocationWire,
  BatchWire,
  EligibleAdmissionWire,
} from "@/lib/api/batches";
import type { FormFeedback } from "@/lib/authz/action-feedback";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { useFinanceMutation } from "../finance/mutations";
import { focusFirstInvalid } from "../shared/forms";

import { INVOICE_STATE_LABEL, outstandingLabel } from "./labels";

// ACA-06 Allocate student (Phase 02-6). Lists admitted students of the batch's
// course and campus who are not in a batch, with their fee position. Fees paid
// → allocate. Otherwise (outstanding, or no live fee invoice — a cancelled one
// is not paid) the allocator must give a payment override reason, which is
// recorded with the outstanding amount and audited. The server decides
// (eligibility, seats, the payment gate) with the rows locked.

type Load =
  | { kind: "loading" }
  | { kind: "ok"; items: EligibleAdmissionWire[] }
  | { kind: "error" };

const MESSAGES: Record<string, string> = {
  batch_full: "This batch is full.",
  batch_not_open: "This batch is not open for allocation.",
  already_allocated:
    "This student is already in a batch. Transfer them instead.",
  admission_not_admitted: "This student's admission can't be allocated.",
  admission_not_available:
    "This student is no longer available. Reload the list.",
  course_mismatch: "This student was admitted to another course.",
  campus_mismatch: "This student was admitted at another campus.",
  student_not_active: "This student is not active.",
};

export function AllocateDialog({
  batch,
  isOpen,
  onOpenChange,
}: {
  batch: BatchWire;
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
}) {
  return (
    <Dialog
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      title={`Allocate a student to ${batch.code}`}
      description={`${batch.course.code} · ${batch.campus.name} · ${batch.available_seats} of ${batch.capacity} seats free`}
      size="lg"
    >
      {(close) => <AllocateForm batch={batch} onClose={close} />}
    </Dialog>
  );
}

function AllocateForm({
  batch,
  onClose,
}: {
  batch: BatchWire;
  onClose: () => void;
}) {
  const { request } = useTenantSession();
  const mutate = useFinanceMutation("batch");
  const formRef = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState("");
  const [load, setLoad] = useState<Load>({ kind: "loading" });
  const [chosen, setChosen] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [errors, setErrors] = useState<{ student?: string; reason?: string }>(
    {},
  );
  const [feedback, setFeedback] = useState<FormFeedback | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    let live = true;
    const params = new URLSearchParams({ limit: "100" });
    if (query) params.set("q", query);
    request<EligibleAdmissionWire[]>(
      `/batches/${batch.id}/eligible-admissions?${params.toString()}`,
    )
      .then((items) => live && setLoad({ kind: "ok", items }))
      .catch(() => live && setLoad({ kind: "error" }));
    return () => {
      live = false;
    };
  }, [batch.id, query, request]);

  const items = load.kind === "ok" ? load.items : [];
  const selected = items.find((item) => item.admission_id === chosen) ?? null;
  const needsOverride = selected !== null && !selected.payment_cleared;

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending) return;
    setFeedback(null);
    const next: typeof errors = {};
    if (!selected) next.student = "Choose a student.";
    else if (needsOverride && !reason.trim()) {
      next.reason = "Enter why this student may join before the fees are paid.";
    }
    setErrors(next);
    if (Object.keys(next).length > 0 || !selected) {
      focusFirstInvalid(formRef.current);
      return;
    }
    setPending(true);
    const outcome = await mutate<AllocationWire>(
      `/batches/${batch.id}/allocations`,
      {
        admission_id: selected.admission_id,
        override_reason: needsOverride ? reason.trim() : null,
      },
      `${selected.student.full_name} allocated to ${batch.code}`,
    );
    setPending(false);
    if (outcome.kind === "done" || outcome.kind === "stale") {
      onClose();
    } else if (outcome.kind === "feedback") {
      setFeedback(outcome.feedback);
    } else {
      const codes = Object.values(outcome.fields);
      if (codes.includes("payment_required")) {
        setErrors({
          reason:
            "The fees are not fully paid. Enter a payment override reason.",
        });
        focusFirstInvalid(formRef.current);
      } else {
        const message = codes.map((code) => MESSAGES[code]).find(Boolean);
        setFeedback({
          tone: "warning",
          title: "The student wasn't allocated",
          body: message ?? "Reload the page and try again.",
        });
      }
    }
  };

  return (
    <div ref={formRef}>
      <Form
        aria-label="Allocate student"
        validationBehavior="aria"
        onSubmit={(event) => void submit(event)}
      >
        {feedback && (
          <Alert tone={feedback.tone} title={feedback.title}>
            {feedback.body}
          </Alert>
        )}
        <Search
          label="Search admitted students"
          isLabelHidden
          placeholder="Search by name, student or admission number"
          onSubmit={(value) => {
            setLoad({ kind: "loading" });
            setChosen(null);
            setQuery(value.trim());
          }}
          onClear={() => {
            setLoad({ kind: "loading" });
            setQuery("");
          }}
        />
        {load.kind === "loading" ? (
          <div aria-busy="true" aria-label="Loading admitted students">
            <SkeletonText lines={4} />
          </div>
        ) : load.kind === "error" ? (
          <Alert tone="error" title="Admitted students couldn't be loaded">
            Close this dialog and try again in a moment.
          </Alert>
        ) : items.length === 0 ? (
          <EmptyState
            title={
              query ? "No admitted students match" : "No students to allocate"
            }
            description={
              query
                ? "Try another name or number."
                : `Students admitted to ${batch.course.code} at ${batch.campus.name} who are not in a batch appear here.`
            }
          />
        ) : (
          <div className="max-h-72 overflow-y-auto pr-1">
            <RadioGroup
              label="Admitted student"
              value={chosen}
              onChange={(value) => {
                setChosen(value);
                setErrors({});
              }}
              options={items.map((item) => ({
                value: item.admission_id,
                label: `${item.student.full_name} · ${item.student.number}`,
                description: `${item.admission_number} · ${
                  item.payment_cleared
                    ? INVOICE_STATE_LABEL.PAID
                    : `${INVOICE_STATE_LABEL[item.invoice_state]} — ${outstandingLabel(item.outstanding_minor)}`
                }`,
              }))}
              isInvalid={Boolean(errors.student)}
              errorMessage={errors.student}
            />
          </div>
        )}
        {needsOverride && selected && (
          <>
            <Alert tone="warning" title="Fees are not fully paid">
              {selected.invoice_state === "NO_INVOICE"
                ? "No fee invoice is live for this admission. "
                : `${outstandingLabel(selected.outstanding_minor)}. `}
              You can still allocate with a payment override. The reason, the
              outstanding amount, your name and the time are recorded.
            </Alert>
            <Textarea
              label="Payment override reason"
              value={reason}
              onChange={(value) => {
                setReason(value);
                setErrors((current) => ({ ...current, reason: undefined }));
              }}
              rows={3}
              maxLength={500}
              showCount
              isRequired
              isInvalid={Boolean(errors.reason)}
              errorMessage={errors.reason}
            />
          </>
        )}
        <div className="flex flex-col-reverse gap-2 pt-2 tablet:flex-row tablet:justify-end">
          <Button variant="secondary" onPress={onClose} isDisabled={pending}>
            Cancel
          </Button>
          <Button
            type="submit"
            isPending={pending}
            isDisabled={load.kind !== "ok"}
          >
            {needsOverride ? "Allocate with override" : "Allocate"}
          </Button>
        </div>
      </Form>
    </div>
  );
}
