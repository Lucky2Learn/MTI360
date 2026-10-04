"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import {
  Alert,
  Button,
  Dialog,
  toast,
  Tooltip,
} from "@/design-system/components";
import { ChevronDownIcon } from "@/design-system/icons";
import { ApiError } from "@/lib/api/errors";
import type { SessionWire } from "@/lib/api/types";
import { formFeedback, type FormFeedback } from "@/lib/authz/action-feedback";
import type { Session } from "@/lib/session/session";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { ALL_CAMPUSES, CampusChooser } from "./choosers";

// CampusSwitcher (T01-04 UI contract §8.8; D04; T01-05 CAMPUS-01). The
// active campus is a VIEW FILTER, not an authorization boundary (D-B1): a
// switch changes which data lists show by default; it never hides features,
// re-checks permissions or changes navigation. The options are exactly the
// session's `campus_options`; "All campuses" only when `all_campuses_allowed`.
// The switch does not rotate the session (no reload): the session read is
// replaced and the page re-fetches its data.

/** The current value shown to the user. */
export function campusLabel(session: Session): string {
  if (session.activeCampus) return session.activeCampus.name;
  return session.allCampusesAllowed ? "All campuses" : "";
}

export function CampusSwitcherTrigger({ onOpen }: { onOpen: () => void }) {
  const { session } = useTenantSession();
  if (session.campusOptions.length === 0) return null;
  const label = campusLabel(session);
  if (session.campusOptions.length === 1) {
    return (
      <p className="block max-w-48 truncate px-2 text-body-sm font-medium text-text-primary">
        {session.campusOptions[0]!.name}
      </p>
    );
  }
  return (
    <Tooltip content={label} placement="bottom">
      <Button
        variant="secondary"
        iconEnd={ChevronDownIcon}
        aria-label={`Campus: ${label}. Switch campus`}
        onPress={onOpen}
      >
        <span className="block max-w-48 truncate">{label}</span>
      </Button>
    </Tooltip>
  );
}

export type CampusSwitchDialogProps = {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
};

export function CampusSwitchDialog({
  isOpen,
  onOpenChange,
}: CampusSwitchDialogProps) {
  const router = useRouter();
  const { session, request, refresh, replace, invalidate } = useTenantSession();
  const [selected, setSelected] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [feedback, setFeedback] = useState<FormFeedback | null>(null);
  const current =
    session.activeCampus?.id ??
    (session.allCampusesAllowed ? ALL_CAMPUSES : null);
  const value = selected ?? current;

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
      const wire = await request<SessionWire>("/session/campus", {
        method: "PUT",
        body: { campus_id: value === ALL_CAMPUSES ? null : value },
      });
      const fresh = replace(wire);
      // Page data follows the new campus from the next requests (D04 rule 9).
      invalidate();
      router.refresh();
      setPending(false);
      close(false);
      toast.success(
        fresh.activeCampus
          ? `Showing ${fresh.activeCampus.name}`
          : "Showing all campuses",
      );
    } catch (error) {
      setPending(false);
      if (error instanceof ApiError && error.code === "NOT_FOUND") {
        setFeedback({
          tone: "warning",
          title: "That campus is no longer available to you.",
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
      title="Switch campus"
      actions={(dismiss) => (
        <>
          <Button variant="secondary" onPress={dismiss} isDisabled={pending}>
            Cancel
          </Button>
          <Button isPending={pending} onPress={() => void submit()}>
            {pending ? "Switching…" : "Switch"}
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
        <CampusChooser
          campuses={session.campusOptions}
          allCampuses={
            session.allCampusesAllowed && session.activeInstitute
              ? { instituteName: session.activeInstitute.name }
              : null
          }
          value={value}
          onChange={setSelected}
          isDisabled={pending}
        />
      </div>
    </Dialog>
  );
}
