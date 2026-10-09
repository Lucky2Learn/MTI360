"use client";

import { useState } from "react";

import { Button } from "@/design-system/components";
import { EditIcon } from "@/design-system/icons";
import type { ApplicationWire } from "@/lib/api/admissions";
import { useTenantSession } from "@/lib/session/SessionProvider";

import {
  StatusTransitionDialog,
  type TransitionOutcome,
} from "../shared/StatusTransitionDialog";

import { AdmitDialog } from "./AdmitDialog";
import { stepComplete, WIZARD_STEPS } from "./ApplicationWizard";
import {
  ADMISSION_APPROVE,
  APPLICATION_REVIEW,
  APPLICATION_UPDATE,
  applicationStepPath,
  DECISION_LABEL,
  STATUS_LABEL,
} from "./labels";
import { useRecordMutation } from "./mutations";

// ADM-06 header actions (Phase 02-2; ADM-08 review and ADM-10 admission as
// dialogs of the detail page, ADR-0021 §14). Each is shown only with its
// permission and when the server says it applies (editable, review_options,
// APPROVED); the API decides again. Counsellors never see Review or Admit.

const REVIEW_MESSAGES: Record<
  string,
  Partial<Record<"to" | "reason", string>>
> = {
  invalid_transition: {
    to: "This application can't move to that status any more.",
  },
  reason_required: { reason: "Enter a reason." },
};

export function ApplicationActions({
  application,
}: {
  application: ApplicationWire;
}) {
  const { can } = useTenantSession();
  const mutate = useRecordMutation("application");
  const [dialog, setDialog] = useState<"review" | "admit" | null>(null);
  const close = (open: boolean) => !open && setDialog(null);
  const nextStep =
    WIZARD_STEPS.find(
      (step) => step.id !== "course" && !stepComplete(step.id, application),
    )?.id ?? "review";

  return (
    <>
      {can(APPLICATION_UPDATE) && application.editable && (
        <Button
          variant="secondary"
          iconStart={EditIcon}
          href={applicationStepPath(application.id, nextStep)}
        >
          {application.status === "DRAFT"
            ? "Continue application"
            : "Make corrections"}
        </Button>
      )}
      {can(APPLICATION_REVIEW) && application.review_options.length > 0 && (
        <Button onPress={() => setDialog("review")}>Review</Button>
      )}
      {can(ADMISSION_APPROVE) && application.status === "APPROVED" && (
        <Button onPress={() => setDialog("admit")}>Approve admission</Button>
      )}
      {dialog === "review" && (
        <StatusTransitionDialog
          isOpen
          onOpenChange={close}
          title={`Review ${application.number}`}
          description={`Current status: ${STATUS_LABEL[application.status]}`}
          choices={application.review_options.map((option) => ({
            value: option.to_status,
            label:
              DECISION_LABEL[option.to_status] ??
              STATUS_LABEL[option.to_status],
            requiresReason: option.requires_reason,
            requiresTarget: false,
          }))}
          onSubmit={async ({ to, reason }): Promise<TransitionOutcome> => {
            const outcome = await mutate(
              `/applications/${application.id}/review`,
              { to_status: to, reason, version: application.version },
              `${application.number}: ${STATUS_LABEL[to as keyof typeof STATUS_LABEL]}`,
            );
            if (outcome.kind === "done" || outcome.kind === "stale")
              return { kind: "done" };
            if (outcome.kind === "feedback") return outcome;
            if (outcome.fields.documents === "documents_not_verified") {
              return {
                kind: "feedback",
                feedback: {
                  tone: "warning",
                  title: "Verify every document first",
                  body: "An application is approved only when all its current documents are verified.",
                },
              };
            }
            const fields = Object.values(outcome.fields).reduce(
              (all, code) => ({ ...all, ...REVIEW_MESSAGES[code] }),
              {},
            );
            return Object.keys(fields).length > 0
              ? { kind: "fields", fields }
              : {
                  kind: "feedback",
                  feedback: {
                    tone: "error",
                    title: "This decision wasn't saved",
                  },
                };
          }}
        />
      )}
      {dialog === "admit" && (
        <AdmitDialog application={application} isOpen onOpenChange={close} />
      )}
    </>
  );
}
