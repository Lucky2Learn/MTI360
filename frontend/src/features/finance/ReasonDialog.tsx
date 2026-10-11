"use client";

import { useRef, useState, type FormEvent, type ReactNode } from "react";

import {
  Alert,
  Button,
  Dialog,
  Form,
  Textarea,
} from "@/design-system/components";
import type { FormFeedback } from "@/lib/authz/action-feedback";

import { focusFirstInvalid } from "../shared/forms";

// A confirmation that needs a written reason (Phase 02-5): failing a cheque
// or demand draft, reversing a payment. The reason is required (the server
// refuses an empty one too) and kept with the record. The feature sends the
// request and maps the outcome; nothing changes on screen until the server
// answers.

export type ReasonOutcome =
  | { kind: "done" }
  | { kind: "feedback"; feedback: FormFeedback }
  | { kind: "reason"; message: string };

export function ReasonDialog({
  isOpen,
  onOpenChange,
  title,
  description,
  reasonLabel,
  reasonDescription,
  confirmLabel,
  onSubmit,
}: {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  title: string;
  description: ReactNode;
  reasonLabel: string;
  reasonDescription?: string;
  confirmLabel: string;
  onSubmit: (reason: string) => Promise<ReasonOutcome>;
}) {
  return (
    <Dialog
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      title={title}
      description={description}
      size="md"
    >
      {(close) => (
        <ReasonForm
          reasonLabel={reasonLabel}
          reasonDescription={reasonDescription}
          confirmLabel={confirmLabel}
          onSubmit={onSubmit}
          onCancel={close}
        />
      )}
    </Dialog>
  );
}

function ReasonForm({
  reasonLabel,
  reasonDescription,
  confirmLabel,
  onSubmit,
  onCancel,
}: {
  reasonLabel: string;
  reasonDescription?: string;
  confirmLabel: string;
  onSubmit: (reason: string) => Promise<ReasonOutcome>;
  onCancel: () => void;
}) {
  const formRef = useRef<HTMLDivElement>(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<FormFeedback | null>(null);
  const [pending, setPending] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending) return;
    setFeedback(null);
    if (!reason.trim()) {
      setError("Enter a reason.");
      focusFirstInvalid(formRef.current);
      return;
    }
    setPending(true);
    const outcome = await onSubmit(reason.trim());
    setPending(false);
    if (outcome.kind === "done") onCancel();
    else if (outcome.kind === "feedback") setFeedback(outcome.feedback);
    else {
      setError(outcome.message);
      focusFirstInvalid(formRef.current);
    }
  };

  return (
    <div ref={formRef}>
      <Form
        aria-label={confirmLabel}
        validationBehavior="aria"
        onSubmit={(event) => void submit(event)}
      >
        {feedback && (
          <Alert tone={feedback.tone} title={feedback.title}>
            {feedback.body}
          </Alert>
        )}
        <Textarea
          label={reasonLabel}
          description={reasonDescription}
          value={reason}
          onChange={(value) => {
            setReason(value);
            setError(null);
          }}
          rows={3}
          maxLength={500}
          showCount
          isRequired
          isInvalid={Boolean(error)}
          errorMessage={error ?? undefined}
        />
        <div className="flex flex-col-reverse gap-2 pt-2 tablet:flex-row tablet:justify-end">
          <Button variant="secondary" onPress={onCancel} isDisabled={pending}>
            Cancel
          </Button>
          <Button type="submit" isPending={pending}>
            {confirmLabel}
          </Button>
        </div>
      </Form>
    </div>
  );
}
