"use client";

import { Alert, Badge } from "@/design-system/components";
import type { DuplicateCandidateWire } from "@/lib/api/admissions";

import { formatDate } from "../shared/format";
import { RecordLink } from "../shared/RecordLink";

import { leadPath, STATUS_LABEL, STATUS_TONE } from "./labels";

// "Possible duplicate lead" (Phase 02-1; blueprint §8, §24). A warning, never
// a gate: the form stays submittable. The candidates come from
// POST /leads/duplicate-check and are only leads the member may already read
// (the server never mentions others, not even a count). "Open lead" opens in
// a new tab so the form in progress is kept. Announced politely (role=status).

export function DuplicateWarning({
  candidates,
}: {
  candidates: DuplicateCandidateWire[];
}) {
  if (candidates.length === 0) return null;
  return (
    <div role="status">
      <Alert tone="warning" title="Possible duplicate lead">
        <p>
          {candidates.length === 1
            ? "A lead you can see has the same mobile number or email."
            : `${candidates.length} leads you can see have the same mobile number or email.`}{" "}
          Check before creating another one.
        </p>
        <ul className="mt-3 flex flex-col gap-3">
          {candidates.map((candidate) => (
            <li key={candidate.id} className="flex flex-col gap-1">
              <span className="flex flex-wrap items-center gap-2">
                <RecordLink href={leadPath(candidate.id)} newTab>
                  {`Open lead: ${candidate.full_name}`}
                </RecordLink>
                <Badge tone={STATUS_TONE[candidate.status]}>
                  {STATUS_LABEL[candidate.status]}
                </Badge>
                <Badge>
                  {`Matched on ${candidate.matched_on.join(" and ")}`}
                </Badge>
              </span>
              <span className="text-caption text-text-secondary">
                {[
                  candidate.course_name,
                  candidate.campus_name ?? "Institute-wide",
                  candidate.owner_name
                    ? `Owner: ${candidate.owner_name}`
                    : "Unassigned",
                  `Created ${formatDate(candidate.created_at)}`,
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </span>
            </li>
          ))}
        </ul>
      </Alert>
    </div>
  );
}
