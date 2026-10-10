"use client";

import { useEffect, useRef, useState } from "react";

import { Combobox } from "@/design-system/components";
import type {
  LeadListItemWire,
  LeadStatus,
  TransitionOptionWire,
} from "@/lib/api/admissions";
import { useTenantSession } from "@/lib/session/SessionProvider";

import {
  StatusTransitionDialog,
  type TransitionOutcome,
} from "../shared/StatusTransitionDialog";

import { STATUS_LABEL } from "./labels";
import { useLeadMutation } from "./mutations";

// "Move to…" for a lead (Phase 02-1; blueprint §9, §21-§22): the detail page,
// the list's row menu and the board's card menu all open this dialog. The
// choices are the lead's `transitions` as computed by the server; the API
// validates the move, the reason, the duplicate link and the version again.

export type MovableLead = {
  id: string;
  full_name: string;
  status: LeadStatus;
  version: number;
  transitions: TransitionOptionWire[];
};

const MESSAGES: Record<
  string,
  Partial<Record<"to" | "reason" | "target", string>>
> = {
  invalid_transition: { to: "This lead can't move to that status any more." },
  reason_required: { reason: "Enter a reason." },
  duplicate_target_invalid: {
    target:
      "Choose another open lead you can see; it can't be this lead or a duplicate.",
  },
};

/** Searches leads the caller can read (by name) for the "original lead" field. */
function OriginalLeadField({
  excludeId,
  value,
  onChange,
  errorMessage,
}: {
  excludeId: string;
  value: string | null;
  onChange: (id: string | null) => void;
  errorMessage?: string;
}) {
  const { request } = useTenantSession();
  const [items, setItems] = useState<{ id: string; label: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  const debounced = (text: string) => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => void search(text), 300);
  };

  const search = async (text: string) => {
    if (text.trim().length < 2) {
      setItems([]);
      return;
    }
    setLoading(true);
    try {
      const query = new URLSearchParams({
        q: text.trim(),
        limit: "10",
        status: "NEW",
      });
      for (const status of [
        "CONTACTED",
        "QUALIFIED",
        "COUNSELLING",
        "INTERESTED",
      ]) {
        query.append("status", status);
      }
      const leads = await request<LeadListItemWire[]>(
        `/leads?${query.toString()}`,
      );
      setItems(
        leads
          .filter((lead) => lead.id !== excludeId)
          .map((lead) => ({
            id: lead.id,
            label: lead.full_name,
            description: [
              lead.interested_course?.code,
              STATUS_LABEL[lead.status],
            ]
              .filter(Boolean)
              .join(" · "),
          })),
      );
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Combobox
      label="Original lead"
      options={items}
      value={value}
      onChange={onChange}
      onInputChange={debounced}
      filtering="manual"
      isLoading={loading}
      emptyMessage="Type at least 2 letters of the name"
      description="The earlier enquiry this one repeats."
      isRequired
      isInvalid={Boolean(errorMessage)}
      errorMessage={errorMessage}
    />
  );
}

export function LeadStatusDialog({
  lead,
  isOpen,
  onOpenChange,
  initialTarget,
}: {
  lead: MovableLead;
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  initialTarget?: LeadStatus | null;
}) {
  const mutate = useLeadMutation();
  return (
    <StatusTransitionDialog
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      title={`Move ${lead.full_name} to…`}
      description={`Current status: ${STATUS_LABEL[lead.status]}`}
      initialTarget={initialTarget ?? null}
      choices={lead.transitions.map((option) => ({
        value: option.to_status,
        label: STATUS_LABEL[option.to_status],
        requiresReason: option.requires_reason,
        requiresTarget: option.requires_duplicate_target,
      }))}
      renderTarget={(field) => (
        <OriginalLeadField excludeId={lead.id} {...field} />
      )}
      onSubmit={async ({
        to,
        reason,
        targetId,
      }): Promise<TransitionOutcome> => {
        const outcome = await mutate(
          `/leads/${lead.id}/transition`,
          {
            to_status: to,
            reason,
            duplicate_of_lead_id: targetId,
            version: lead.version,
          },
          `${lead.full_name} moved to ${STATUS_LABEL[to as LeadStatus]}`,
        );
        if (outcome.kind !== "fields") return outcome;
        const fields = Object.values(outcome.fields).reduce(
          (all, code) => ({ ...all, ...MESSAGES[code] }),
          {},
        );
        return Object.keys(fields).length > 0
          ? { kind: "fields", fields }
          : {
              kind: "feedback",
              feedback: {
                tone: "error",
                title: "This status change wasn't saved",
              },
            };
      }}
    />
  );
}
