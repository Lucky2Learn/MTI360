"use client";

import { useEffect, useState } from "react";

import {
  Alert,
  Button,
  Dialog,
  RadioGroup,
  Skeleton,
} from "@/design-system/components";
import type {
  ApplicationWire,
  StudentCandidateWire,
} from "@/lib/api/admissions";
import type { FormFeedback } from "@/lib/authz/action-feedback";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { formatDate } from "../shared/format";

import { useRecordMutation } from "./mutations";

// ADM-10 Admission approval (Phase 02-2; ADR-0021 §2, §6, Y6). Approving the
// admission issues the admission number and creates the student — or links
// the student the approver chooses explicitly. Students with the same mobile
// or email (only those the approver may see) are offered; nothing is linked
// automatically and nothing is preselected except "create a new student".
// No payment is required at this step (L3).

const NEW = "new";

function candidateLabel(candidate: StudentCandidateWire): string {
  return `Link to ${candidate.student_number} · ${candidate.full_name}`;
}

function candidateDescription(candidate: StudentCandidateWire): string {
  const parts = [
    candidate.date_of_birth
      ? `Born ${formatDate(candidate.date_of_birth)}`
      : null,
    `Campus ${candidate.campus_code}`,
    `Same ${candidate.matched_on.join(" and ")}`,
  ];
  return parts.filter(Boolean).join(" · ");
}

export function AdmitDialog({
  application,
  isOpen,
  onOpenChange,
}: {
  application: ApplicationWire;
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
}) {
  const { request } = useTenantSession();
  const mutate = useRecordMutation("application");
  const [candidates, setCandidates] = useState<StudentCandidateWire[] | null>(
    null,
  );
  const [loadFailed, setLoadFailed] = useState(false);
  const [choice, setChoice] = useState<string>(NEW);
  const [pending, setPending] = useState(false);
  const [feedback, setFeedback] = useState<FormFeedback | null>(null);

  useEffect(() => {
    let active = true;
    request<{ candidates: StudentCandidateWire[] }>(
      `/applications/${application.id}/student-candidates`,
    )
      .then((data) => active && setCandidates(data.candidates))
      .catch(() => active && setLoadFailed(true));
    return () => {
      active = false;
    };
  }, [application.id, request]);

  const admit = async (close: () => void) => {
    setPending(true);
    setFeedback(null);
    const body =
      choice === NEW
        ? { student: "new", version: application.version }
        : {
            student: "existing",
            student_id: choice,
            version: application.version,
          };
    const outcome = await mutate(
      `/applications/${application.id}/admit`,
      body,
      `${application.full_name} admitted`,
    );
    setPending(false);
    if (outcome.kind === "done" || outcome.kind === "stale") {
      close();
    } else if (outcome.kind === "fields") {
      setFeedback({
        tone: "error",
        title:
          outcome.fields.student_id === "student_not_available"
            ? "That student can't be linked"
            : "The admission wasn't approved",
        body:
          outcome.fields.student_id === "student_not_available"
            ? "Choose another matching student, or create a new student."
            : "The application is no longer approved. Reload it to see its status.",
      });
    } else {
      setFeedback(outcome.feedback);
    }
  };

  return (
    <Dialog
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      title={`Approve admission for ${application.full_name}`}
      description={`${application.course.code} · ${application.campus.name}. An admission number is issued and the student record is created or linked.`}
      size="md"
    >
      {(close) => (
        <div className="flex flex-col gap-4">
          {feedback && (
            <Alert tone={feedback.tone} title={feedback.title}>
              {feedback.body}
            </Alert>
          )}
          {candidates === null && !loadFailed ? (
            <div aria-busy="true" aria-label="Looking for matching students">
              <Skeleton height="text" />
              <Skeleton height="text" />
            </div>
          ) : (
            <>
              {loadFailed && (
                <Alert
                  tone="warning"
                  title="Matching students couldn't be checked"
                >
                  You can still create a new student record.
                </Alert>
              )}
              {candidates && candidates.length > 0 && (
                <Alert tone="info" title="Possible existing student">
                  A student with the same contact details exists. Link the
                  application only if it is the same person; a shared family
                  phone is common.
                </Alert>
              )}
              <RadioGroup
                label="Student record"
                options={[
                  {
                    value: NEW,
                    label: "Create a new student",
                    description: "A new student number is issued.",
                  },
                  ...(candidates ?? []).map((candidate) => ({
                    value: candidate.id,
                    label: candidateLabel(candidate),
                    description: candidateDescription(candidate),
                  })),
                ]}
                value={choice}
                onChange={setChoice}
              />
            </>
          )}
          <div className="flex flex-col-reverse gap-2 pt-2 tablet:flex-row tablet:justify-end">
            <Button variant="secondary" onPress={close} isDisabled={pending}>
              Cancel
            </Button>
            <Button
              onPress={() => void admit(close)}
              isPending={pending}
              isDisabled={candidates === null && !loadFailed}
            >
              Approve admission
            </Button>
          </div>
        </div>
      )}
    </Dialog>
  );
}
