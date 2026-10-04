"use client";

import { useState } from "react";

import { Alert, Button, Dialog, Tooltip } from "@/design-system/components";
import { ChevronDownIcon, InstituteIcon } from "@/design-system/icons";
import { ApiError } from "@/lib/api/errors";
import type { SessionWire } from "@/lib/api/types";
import { formFeedback, type FormFeedback } from "@/lib/authz/action-feedback";
import { assignLocation } from "@/lib/session/document";
import { destinationFor } from "@/lib/session/routes";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { InstituteChooser } from "./choosers";

// TenantContext — institute context in the shell header (T01-04 UI contract
// §8.8; CLAUDE.md §26). Every value comes from the server session; it is a
// UX control, not a security authority. Switching sends the chosen id to
// PUT /session/tenant, which decides; on success the session is rotated and
// the page is left with a FULL document navigation, so nothing cached for
// the previous institute survives (`next` is not honoured, §6.1).

export function TenantContextTrigger({ onOpen }: { onOpen: () => void }) {
  const { session } = useTenantSession();
  const name = session.activeInstitute?.name ?? "";
  if (session.institutes.length <= 1) {
    return (
      <p className="flex min-w-0 items-center gap-2 px-2 text-body-sm font-medium text-text-primary">
        <InstituteIcon aria-hidden="true" className="size-4 shrink-0" />
        <span className="block max-w-48 truncate">{name}</span>
      </p>
    );
  }
  return (
    <Tooltip content={name} placement="bottom">
      <Button
        variant="secondary"
        iconStart={InstituteIcon}
        iconEnd={ChevronDownIcon}
        aria-label={`Institute: ${name}. Switch institute`}
        onPress={onOpen}
      >
        <span className="block max-w-48 truncate">{name}</span>
      </Button>
    </Tooltip>
  );
}

export type InstituteSwitchDialogProps = {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
};

export function InstituteSwitchDialog({
  isOpen,
  onOpenChange,
}: InstituteSwitchDialogProps) {
  const { session, request, refresh } = useTenantSession();
  const [selected, setSelected] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [feedback, setFeedback] = useState<FormFeedback | null>(null);
  const value = selected ?? session.activeInstitute?.id ?? null;

  const close = (open: boolean) => {
    if (!open) {
      setSelected(null);
      setFeedback(null);
    }
    onOpenChange(open);
  };

  const submit = async () => {
    if (pending || !value) return;
    setPending(true);
    setFeedback(null);
    try {
      const fresh = await request<SessionWire>("/session/tenant", {
        method: "PUT",
        body: { tenant_id: value },
      });
      assignLocation(destinationFor(fresh.status, null));
    } catch (error) {
      setPending(false);
      if (
        error instanceof ApiError &&
        (error.code === "NOT_FOUND" || error.code === "CONFLICT")
      ) {
        setFeedback({
          tone: "warning",
          title: "That institute is no longer available to you.",
        });
        setSelected(null);
        await refresh().catch(() => null);
        return;
      }
      setFeedback(formFeedback(error));
    }
  };

  return (
    <Dialog
      isOpen={isOpen}
      onOpenChange={close}
      title="Switch institute"
      actions={(dismiss) => (
        <>
          <Button variant="secondary" onPress={dismiss} isDisabled={pending}>
            Cancel
          </Button>
          <Button isPending={pending} onPress={() => void submit()}>
            {pending ? "Opening…" : "Switch"}
          </Button>
        </>
      )}
    >
      <div className="flex flex-col gap-4">
        {feedback && (
          <Alert tone={feedback.tone} title={feedback.title}>
            {feedback.body}
          </Alert>
        )}
        <InstituteChooser
          institutes={session.institutes}
          value={value}
          onChange={setSelected}
          isDisabled={pending}
        />
      </div>
    </Dialog>
  );
}
