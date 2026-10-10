"use client";

import { useRef, useState, type FormEvent, type ReactNode } from "react";

import {
  Alert,
  Button,
  Dialog,
  Form,
  Select,
  Textarea,
} from "@/design-system/components";
import type { FormFeedback } from "@/lib/authz/action-feedback";

import { focusFirstInvalid } from "./forms";

// StatusTransitionDialog (Phase 02-1; blueprint §21-§22, §28): change the
// status of a record (a lead now; applications and documents in 02-2). The
// target list is the server's own rule for the record (its allowed
// transitions), so the client never decides what is allowed; the server
// validates again and its answer wins. A reason is required when the target
// says so; some targets need another record (e.g. the original of a
// duplicate), supplied by the feature through `renderTarget`. Nothing changes
// on screen until the server answers (no optimistic update).

export type TransitionChoice = {
  value: string;
  label: string;
  requiresReason: boolean;
  requiresTarget: boolean;
};

export type TransitionInput = {
  to: string;
  reason: string | null;
  targetId: string | null;
};

/** `done` closes the dialog; otherwise the dialog shows the outcome. */
export type TransitionOutcome =
  | { kind: "done" }
  | { kind: "feedback"; feedback: FormFeedback }
  | {
      kind: "fields";
      fields: Partial<Record<"to" | "reason" | "target", string>>;
    };

export type StatusTransitionDialogProps = {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  /** e.g. "Move Arjun Nair to…" */
  title: string;
  /** e.g. "Current status: New" */
  description?: ReactNode;
  choices: TransitionChoice[];
  initialTarget?: string | null;
  reasonMaxLength?: number;
  targetLabel?: string;
  renderTarget?: (field: {
    value: string | null;
    onChange: (id: string | null) => void;
    errorMessage?: string;
  }) => ReactNode;
  onSubmit: (input: TransitionInput) => Promise<TransitionOutcome>;
};

export function StatusTransitionDialog({
  isOpen,
  onOpenChange,
  title,
  description,
  choices,
  initialTarget = null,
  reasonMaxLength = 500,
  renderTarget,
  onSubmit,
}: StatusTransitionDialogProps) {
  return (
    <Dialog
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      title={title}
      description={description}
      size="md"
    >
      {(close) => (
        <TransitionForm
          choices={choices}
          initialTarget={initialTarget}
          reasonMaxLength={reasonMaxLength}
          renderTarget={renderTarget}
          onSubmit={onSubmit}
          onCancel={close}
          onDone={close}
        />
      )}
    </Dialog>
  );
}

function TransitionForm({
  choices,
  initialTarget,
  reasonMaxLength,
  renderTarget,
  onSubmit,
  onCancel,
  onDone,
}: {
  choices: TransitionChoice[];
  initialTarget: string | null;
  reasonMaxLength: number;
  renderTarget: StatusTransitionDialogProps["renderTarget"];
  onSubmit: (input: TransitionInput) => Promise<TransitionOutcome>;
  onCancel: () => void;
  onDone: () => void;
}) {
  const formRef = useRef<HTMLDivElement>(null);
  const [to, setTo] = useState<string | null>(
    choices.some((c) => c.value === initialTarget) ? initialTarget : null,
  );
  const [reason, setReason] = useState("");
  const [target, setTarget] = useState<string | null>(null);
  const [errors, setErrors] = useState<
    Partial<Record<"to" | "reason" | "target", string>>
  >({});
  const [feedback, setFeedback] = useState<FormFeedback | null>(null);
  const [pending, setPending] = useState(false);
  const choice = choices.find((c) => c.value === to);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending) return;
    const next: typeof errors = {};
    if (!choice) next.to = "Choose a status.";
    if (choice?.requiresReason && !reason.trim())
      next.reason = "Enter a reason.";
    if (choice?.requiresTarget && !target)
      next.target = "Choose the original lead.";
    setErrors(next);
    setFeedback(null);
    if (Object.keys(next).length > 0 || !choice) {
      focusFirstInvalid(formRef.current);
      return;
    }
    setPending(true);
    const outcome = await onSubmit({
      to: choice.value,
      reason: reason.trim() || null,
      targetId: choice.requiresTarget ? target : null,
    });
    setPending(false);
    if (outcome.kind === "done") {
      onDone();
    } else if (outcome.kind === "fields") {
      setErrors(outcome.fields);
      focusFirstInvalid(formRef.current);
    } else {
      setFeedback(outcome.feedback);
    }
  };

  return (
    <div ref={formRef}>
      <Form
        aria-label="Change status"
        validationBehavior="aria"
        onSubmit={(event) => void submit(event)}
      >
        {feedback && (
          <Alert tone={feedback.tone} title={feedback.title}>
            {feedback.body}
          </Alert>
        )}
        <Select
          label="New status"
          options={choices.map((c) => ({ id: c.value, label: c.label }))}
          value={to}
          onChange={(value) => {
            setTo(value);
            setErrors({});
          }}
          isRequired
          isInvalid={Boolean(errors.to)}
          errorMessage={errors.to}
        />
        {choice?.requiresTarget &&
          renderTarget?.({
            value: target,
            onChange: (id) => {
              setTarget(id);
              setErrors((current) => ({ ...current, target: undefined }));
            },
            errorMessage: errors.target,
          })}
        <Textarea
          label={choice?.requiresReason ? "Reason" : "Reason (optional)"}
          value={reason}
          onChange={(value) => {
            setReason(value);
            setErrors((current) => ({ ...current, reason: undefined }));
          }}
          rows={3}
          maxLength={reasonMaxLength}
          showCount
          isRequired={Boolean(choice?.requiresReason)}
          isInvalid={Boolean(errors.reason)}
          errorMessage={errors.reason}
        />
        <div className="flex flex-col-reverse gap-2 pt-2 tablet:flex-row tablet:justify-end">
          <Button variant="secondary" onPress={onCancel} isDisabled={pending}>
            Cancel
          </Button>
          <Button type="submit" isPending={pending}>
            Save status
          </Button>
        </div>
      </Form>
    </div>
  );
}
