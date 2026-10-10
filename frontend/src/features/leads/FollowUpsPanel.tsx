"use client";

import { useRef, useState, type FormEvent } from "react";

import {
  Alert,
  AlertDialog,
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  DatePicker,
  Dialog,
  EmptyState,
  Form,
  Select,
  Textarea,
  TimePicker,
} from "@/design-system/components";
import { AddIcon, ScheduleIcon } from "@/design-system/icons";
import type {
  AssigneeWire,
  FollowUpKind,
  FollowUpWire,
} from "@/lib/api/admissions";
import type { FormFeedback } from "@/lib/authz/action-feedback";
import { PermissionGate } from "@/lib/authz/PermissionGate";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { formatDateTime } from "../shared/format";
import { focusFirstInvalid } from "../shared/forms";
import { MemberPicker } from "../shared/MemberPicker";

import {
  FOLLOW_UP_KIND_LABEL,
  LEAD_ASSIGN,
  LEAD_UPDATE,
  options,
} from "./labels";
import { useLeadMutation } from "./mutations";

// Follow-ups of a lead (Phase 02-1; blueprint §11, §21): lightweight
// scheduled tasks — no reminders, notifications or messages are sent. Open
// ones first (overdue marked with text), then the closed history. Schedule,
// reschedule, complete (with an optional outcome) and cancel need
// lead.update; choosing another assignee needs the assignee list
// (lead.assign), otherwise the server picks the owner or the creator.

type Draft = {
  date: string | null;
  time: string | null;
  kind: FollowUpKind | null;
  note: string;
  assignee: string | null;
};

function localParts(iso: string): { date: string; time: string } {
  const value = new Date(iso);
  const local = new Date(value.getTime() - value.getTimezoneOffset() * 60_000)
    .toISOString()
    .slice(0, 16);
  return { date: local.slice(0, 10), time: local.slice(11, 16) };
}

function tomorrow(): string {
  const value = new Date(Date.now() + 86_400_000);
  return localParts(value.toISOString()).date;
}

const FIELD_ERRORS: Record<string, [keyof Draft, string]> = {
  out_of_range: ["date", "Choose a date within the next year."],
  timezone_required: ["date", "Choose a date and time."],
  owner_not_eligible: [
    "assignee",
    "This team member doesn't work with this lead's campus.",
  ],
};

function FollowUpForm({
  leadId,
  campusId,
  existing,
  onDone,
}: {
  leadId: string;
  campusId: string | null;
  existing?: FollowUpWire;
  onDone: () => void;
}) {
  const { can, request } = useTenantSession();
  const mutate = useLeadMutation();
  const wrapper = useRef<HTMLDivElement>(null);
  const parts = existing ? localParts(existing.due_at) : null;
  const [draft, setDraft] = useState<Draft>({
    date: parts?.date ?? tomorrow(),
    time: parts?.time ?? "10:00",
    kind: existing?.kind ?? "CALL",
    note: existing?.note ?? "",
    assignee: existing?.assignee?.membership_id ?? null,
  });
  const [errors, setErrors] = useState<Partial<Record<keyof Draft, string>>>(
    {},
  );
  const [feedback, setFeedback] = useState<FormFeedback | null>(null);
  const [pending, setPending] = useState(false);
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => {
    setDraft((current) => ({ ...current, [key]: value }));
    setErrors((current) => ({ ...current, [key]: undefined }));
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending) return;
    const problems: typeof errors = {};
    if (!draft.date) problems.date = "Choose a date.";
    if (!draft.time) problems.time = "Choose a time.";
    if (!draft.kind) problems.kind = "Choose a type.";
    setErrors(problems);
    if (Object.keys(problems).length > 0) {
      focusFirstInvalid(wrapper.current);
      return;
    }
    setPending(true);
    setFeedback(null);
    const dueAt = new Date(`${draft.date}T${draft.time}`).toISOString();
    const body = {
      due_at: dueAt,
      kind: draft.kind,
      note: draft.note.trim() || null,
      ...(draft.assignee ? { assignee_membership_id: draft.assignee } : {}),
    };
    const outcome = existing
      ? await mutate(
          `/lead-follow-ups/${existing.id}`,
          { ...body, version: existing.version },
          "Follow-up rescheduled",
          "PATCH",
        )
      : await mutate(
          `/leads/${leadId}/follow-ups`,
          body,
          "Follow-up scheduled",
        );
    setPending(false);
    if (outcome.kind === "done") onDone();
    else if (outcome.kind === "fields") {
      const mapped: typeof errors = {};
      for (const code of Object.values(outcome.fields)) {
        const rule = FIELD_ERRORS[code];
        if (rule) mapped[rule[0]] = rule[1];
      }
      if (Object.keys(mapped).length === 0) {
        setFeedback({ tone: "error", title: "This follow-up wasn't saved" });
      }
      setErrors(mapped);
      focusFirstInvalid(wrapper.current);
    } else setFeedback(outcome.feedback);
  };

  const campusParam = campusId ?? "none";
  return (
    <div ref={wrapper}>
      <Form
        aria-label={existing ? "Reschedule follow-up" : "Schedule follow-up"}
        validationBehavior="aria"
        onSubmit={(event) => void submit(event)}
      >
        {feedback && (
          <Alert tone={feedback.tone} title={feedback.title}>
            {feedback.body}
          </Alert>
        )}
        <div className="grid grid-cols-1 gap-4 tablet:grid-cols-2">
          <DatePicker
            label="Date"
            value={draft.date}
            onChange={(value) => set("date", value)}
            isRequired
            isInvalid={Boolean(errors.date)}
            errorMessage={errors.date}
          />
          <TimePicker
            label="Time"
            value={draft.time}
            onChange={(value) => set("time", value)}
            isRequired
            isInvalid={Boolean(errors.time)}
            errorMessage={errors.time}
          />
        </div>
        <Select
          label="Type"
          options={options(FOLLOW_UP_KIND_LABEL)}
          value={draft.kind}
          onChange={(value) => set("kind", value as FollowUpKind | null)}
          description="A label for your planning; nothing is sent to the enquirer."
          isRequired
          isInvalid={Boolean(errors.kind)}
          errorMessage={errors.kind}
        />
        {can(LEAD_ASSIGN) && (
          <MemberPicker
            label="Assigned to"
            loadKey={campusParam}
            load={async () =>
              (
                await request<{ items: AssigneeWire[] }>(
                  `/leads/assignees?campus_id=${encodeURIComponent(campusParam)}`,
                )
              ).items.map((m) => ({
                id: m.membership_id,
                label: m.display_name,
              }))
            }
            current={
              existing?.assignee
                ? {
                    id: existing.assignee.membership_id,
                    label: existing.assignee.display_name,
                  }
                : null
            }
            value={draft.assignee}
            onChange={(value) => set("assignee", value)}
            description="Leave empty for the lead owner (or you, when there is none)."
            errorMessage={errors.assignee}
          />
        )}
        <Textarea
          label="What to do (optional)"
          value={draft.note}
          onChange={(value) => set("note", value)}
          rows={3}
          maxLength={1000}
          showCount
        />
        <div className="flex flex-col-reverse gap-2 pt-2 tablet:flex-row tablet:justify-end">
          <Button variant="secondary" onPress={onDone} isDisabled={pending}>
            Cancel
          </Button>
          <Button type="submit" isPending={pending}>
            {existing ? "Save" : "Schedule"}
          </Button>
        </div>
      </Form>
    </div>
  );
}

function CompleteForm({
  item,
  onDone,
}: {
  item: FollowUpWire;
  onDone: () => void;
}) {
  const mutate = useLeadMutation();
  const [outcome, setOutcome] = useState("");
  const [feedback, setFeedback] = useState<FormFeedback | null>(null);
  const [pending, setPending] = useState(false);
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending) return;
    setPending(true);
    const result = await mutate(
      `/lead-follow-ups/${item.id}/complete`,
      { outcome: outcome.trim() || null, version: item.version },
      "Follow-up completed",
    );
    setPending(false);
    if (result.kind === "done") onDone();
    else
      setFeedback(
        result.kind === "feedback"
          ? result.feedback
          : { tone: "error", title: "This follow-up wasn't saved" },
      );
  };
  return (
    <Form
      aria-label="Complete follow-up"
      validationBehavior="aria"
      onSubmit={(event) => void submit(event)}
    >
      {feedback && (
        <Alert tone={feedback.tone} title={feedback.title}>
          {feedback.body}
        </Alert>
      )}
      <Textarea
        label="Outcome (optional)"
        value={outcome}
        onChange={setOutcome}
        rows={3}
        maxLength={1000}
        showCount
      />
      <div className="flex flex-col-reverse gap-2 pt-2 tablet:flex-row tablet:justify-end">
        <Button variant="secondary" onPress={onDone} isDisabled={pending}>
          Cancel
        </Button>
        <Button type="submit" isPending={pending}>
          Mark done
        </Button>
      </div>
    </Form>
  );
}

type Open =
  | { kind: "schedule" }
  | { kind: "reschedule"; item: FollowUpWire }
  | { kind: "complete"; item: FollowUpWire }
  | { kind: "cancel"; item: FollowUpWire }
  | null;

function FollowUpRow({
  item,
  onOpen,
}: {
  item: FollowUpWire;
  onOpen: (open: Open) => void;
}) {
  const closed = item.status !== "OPEN";
  return (
    <li className="flex flex-col gap-2 border-b border-border-subtle pb-3 last:border-0 last:pb-0">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-body-sm font-medium text-text-primary">
          {FOLLOW_UP_KIND_LABEL[item.kind]}
        </span>
        <time
          dateTime={item.due_at}
          className="text-body-sm text-text-secondary"
        >
          {formatDateTime(item.due_at)}
        </time>
        {item.overdue && <Badge tone="error">Overdue</Badge>}
        {item.status === "DONE" && <Badge tone="success">Done</Badge>}
        {item.status === "CANCELLED" && <Badge>Cancelled</Badge>}
      </div>
      {item.note && (
        <p className="text-body-sm break-words whitespace-pre-wrap text-text-primary">
          {item.note}
        </p>
      )}
      {item.outcome && (
        <p className="text-body-sm break-words whitespace-pre-wrap text-text-secondary">
          {`Outcome: ${item.outcome}`}
        </p>
      )}
      <p className="text-caption text-text-secondary">
        {closed && item.completed_by
          ? `Closed by ${item.completed_by.display_name}`
          : `Assigned to ${item.assignee?.display_name ?? "—"}`}
      </p>
      {!closed && (
        <PermissionGate permission={LEAD_UPDATE}>
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              onPress={() => onOpen({ kind: "complete", item })}
            >
              Mark done
            </Button>
            <Button
              size="sm"
              variant="secondary"
              onPress={() => onOpen({ kind: "reschedule", item })}
            >
              Reschedule
            </Button>
            <Button
              size="sm"
              variant="tertiary"
              onPress={() => onOpen({ kind: "cancel", item })}
            >
              Cancel follow-up
            </Button>
          </div>
        </PermissionGate>
      )}
    </li>
  );
}

export function FollowUpsPanel({
  leadId,
  campusId,
  followUps,
}: {
  leadId: string;
  campusId: string | null;
  followUps: FollowUpWire[];
}) {
  const mutate = useLeadMutation();
  const [open, setOpen] = useState<Open>(null);
  const [cancelling, setCancelling] = useState(false);
  const pending = followUps.filter((item) => item.status === "OPEN");
  const history = followUps.filter((item) => item.status !== "OPEN");
  const close = () => setOpen(null);

  return (
    <Card as="section">
      <CardHeader
        title="Follow-ups"
        titleAs="h2"
        actions={
          <PermissionGate permission={LEAD_UPDATE}>
            <Button
              size="sm"
              variant="secondary"
              iconStart={AddIcon}
              onPress={() => setOpen({ kind: "schedule" })}
            >
              Schedule
            </Button>
          </PermissionGate>
        }
      />
      <CardBody>
        {followUps.length === 0 ? (
          <EmptyState
            icon={ScheduleIcon}
            title="No follow-ups yet"
            description="Schedule the next call, message or visit so it isn't missed."
          />
        ) : (
          <div className="flex flex-col gap-4">
            {pending.length > 0 && (
              <ul aria-label="Open follow-ups" className="flex flex-col gap-3">
                {pending.map((item) => (
                  <FollowUpRow key={item.id} item={item} onOpen={setOpen} />
                ))}
              </ul>
            )}
            {history.length > 0 && (
              <details className="text-body-sm">
                <summary className="cursor-pointer text-text-secondary">
                  {`Closed follow-ups (${history.length})`}
                </summary>
                <ul
                  aria-label="Closed follow-ups"
                  className="mt-3 flex flex-col gap-3"
                >
                  {history.map((item) => (
                    <FollowUpRow key={item.id} item={item} onOpen={setOpen} />
                  ))}
                </ul>
              </details>
            )}
          </div>
        )}
      </CardBody>
      <Dialog
        isOpen={open?.kind === "schedule" || open?.kind === "reschedule"}
        onOpenChange={(isOpen) => !isOpen && close()}
        title={
          open?.kind === "reschedule"
            ? "Reschedule follow-up"
            : "Schedule a follow-up"
        }
      >
        {open?.kind === "schedule" || open?.kind === "reschedule" ? (
          <FollowUpForm
            leadId={leadId}
            campusId={campusId}
            existing={open.kind === "reschedule" ? open.item : undefined}
            onDone={close}
          />
        ) : null}
      </Dialog>
      <Dialog
        isOpen={open?.kind === "complete"}
        onOpenChange={(isOpen) => !isOpen && close()}
        title="Mark follow-up done"
      >
        {open?.kind === "complete" ? (
          <CompleteForm item={open.item} onDone={close} />
        ) : null}
      </Dialog>
      <AlertDialog
        isOpen={open?.kind === "cancel"}
        onOpenChange={(isOpen) => !isOpen && close()}
        title="Cancel this follow-up?"
        description="It stays in the lead's history as cancelled."
        confirmLabel="Cancel follow-up"
        cancelLabel="Keep it"
        tone="destructive"
        isPending={cancelling}
        onConfirm={() => {
          if (open?.kind !== "cancel") return;
          setCancelling(true);
          void mutate(
            `/lead-follow-ups/${open.item.id}/cancel`,
            { version: open.item.version },
            "Follow-up cancelled",
          ).finally(() => {
            setCancelling(false);
            close();
          });
        }}
      />
    </Card>
  );
}
