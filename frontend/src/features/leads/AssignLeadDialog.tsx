"use client";

import { useRef, useState, type FormEvent } from "react";

import {
  Alert,
  Button,
  Dialog,
  Form,
  Select,
} from "@/design-system/components";
import type { AssigneeWire } from "@/lib/api/admissions";
import type { FormFeedback } from "@/lib/authz/action-feedback";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { focusFirstInvalid } from "../shared/forms";
import { MemberPicker } from "../shared/MemberPicker";

import { useLeadMutation } from "./mutations";

// Assign… (Phase 02-1; blueprint §10, §21): owner and campus together, with
// lead.assign. The campus list is the caller's own campuses plus
// "Institute-wide" (the pool); the owner list comes from
// GET /leads/assignees for the chosen campus (eligible members only). The
// server re-checks both campuses and the owner's eligibility.

export const INSTITUTE_WIDE = "pool";

export type AssignableLead = {
  id: string;
  full_name: string;
  version: number;
  campus: { id: string; code: string; name?: string } | null;
  owner: { membership_id?: string; display_name: string } | null;
};

const MESSAGES: Record<string, Partial<Record<"owner" | "campus", string>>> = {
  owner_not_eligible: {
    owner:
      "This team member doesn't work with the chosen campus or can't take leads.",
  },
  campus_not_available: {
    campus: "Choose one of your campuses, or institute-wide.",
  },
};

export function AssignLeadDialog({
  lead,
  isOpen,
  onOpenChange,
}: {
  lead: AssignableLead;
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
}) {
  return (
    <Dialog
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      title={`Assign ${lead.full_name}`}
      description="Choose who works this lead and which campus it belongs to."
    >
      {(close) => <AssignForm lead={lead} onDone={close} />}
    </Dialog>
  );
}

function AssignForm({
  lead,
  onDone,
}: {
  lead: AssignableLead;
  onDone: () => void;
}) {
  const { session, request } = useTenantSession();
  const mutate = useLeadMutation();
  const wrapper = useRef<HTMLDivElement>(null);
  const [campus, setCampus] = useState<string>(
    lead.campus?.id ?? INSTITUTE_WIDE,
  );
  const [owner, setOwner] = useState<string | null>(
    lead.owner?.membership_id ?? null,
  );
  const [errors, setErrors] = useState<
    Partial<Record<"owner" | "campus", string>>
  >({});
  const [feedback, setFeedback] = useState<FormFeedback | null>(null);
  const [pending, setPending] = useState(false);

  const campusOptions = [
    { id: INSTITUTE_WIDE, label: "Institute-wide (all campuses)" },
    ...session.campusOptions.map((c) => ({ id: c.id, label: c.name })),
    ...(lead.campus &&
    !session.campusOptions.some((c) => c.id === lead.campus?.id)
      ? [{ id: lead.campus.id, label: lead.campus.name ?? lead.campus.code }]
      : []),
  ];
  const campusParam = campus === INSTITUTE_WIDE ? "none" : campus;

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending) return;
    setPending(true);
    setErrors({});
    setFeedback(null);
    const outcome = await mutate(
      `/leads/${lead.id}/assign`,
      {
        owner_membership_id: owner,
        campus_id: campus === INSTITUTE_WIDE ? null : campus,
        version: lead.version,
      },
      `${lead.full_name} assigned`,
    );
    setPending(false);
    if (outcome.kind === "done") onDone();
    else if (outcome.kind === "fields") {
      const mapped = Object.values(outcome.fields).reduce(
        (all, code) => ({ ...all, ...MESSAGES[code] }),
        {},
      );
      setErrors(mapped);
      focusFirstInvalid(wrapper.current);
    } else setFeedback(outcome.feedback);
  };

  return (
    <div ref={wrapper}>
      <Form
        aria-label="Assign lead"
        validationBehavior="aria"
        onSubmit={(event) => void submit(event)}
      >
        {feedback && (
          <Alert tone={feedback.tone} title={feedback.title}>
            {feedback.body}
          </Alert>
        )}
        <Select
          label="Campus"
          options={campusOptions}
          value={campus}
          onChange={(value) => {
            setCampus(value ?? INSTITUTE_WIDE);
            setErrors({});
          }}
          description="Institute-wide leads are visible to staff of every campus."
          isInvalid={Boolean(errors.campus)}
          errorMessage={errors.campus}
        />
        <MemberPicker
          label="Owner"
          allowUnassigned
          loadKey={campusParam}
          load={async () =>
            (
              await request<{ items: AssigneeWire[] }>(
                `/leads/assignees?campus_id=${encodeURIComponent(campusParam)}`,
              )
            ).items.map((m) => ({ id: m.membership_id, label: m.display_name }))
          }
          current={
            lead.owner?.membership_id
              ? { id: lead.owner.membership_id, label: lead.owner.display_name }
              : null
          }
          value={owner}
          onChange={(value) => {
            setOwner(value);
            setErrors({});
          }}
          description="Only team members who work with this campus are listed."
          errorMessage={errors.owner}
        />
        <div className="flex flex-col-reverse gap-2 pt-2 tablet:flex-row tablet:justify-end">
          <Button variant="secondary" onPress={onDone} isDisabled={pending}>
            Cancel
          </Button>
          <Button type="submit" isPending={pending}>
            Save assignment
          </Button>
        </div>
      </Form>
    </div>
  );
}
