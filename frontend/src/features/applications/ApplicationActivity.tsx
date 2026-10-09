import type {
  ApplicationActivityWire,
  ApplicationStatus,
} from "@/lib/api/admissions";

import {
  ActivityFeed,
  type ActivityDescription,
} from "../activity/ActivityFeed";

import {
  DETAIL_FIELD_LABEL,
  DOCUMENT_TYPE_LABEL,
  STATUS_LABEL,
} from "./labels";

// An application's history (Phase 02-2; ADR-0021 §12): every recorded event,
// newest first, with names resolved by the server. Shared by ADM-06 and the
// Student 360 timeline. Details hold statuses, types, field names and
// numbers only; never file contents.

const text = (value: unknown): string | null =>
  typeof value === "string" && value ? value : null;
const status = (value: unknown): string =>
  STATUS_LABEL[value as ApplicationStatus] ?? "another status";
const documentType = (value: unknown): string =>
  DOCUMENT_TYPE_LABEL[value as keyof typeof DOCUMENT_TYPE_LABEL] ?? "Document";

export function describeApplicationActivity(activity: {
  kind: string;
  details: Record<string, unknown>;
}): ActivityDescription {
  const d = activity.details;
  switch (activity.kind) {
    case "CREATED":
      return {
        title: d.from_lead
          ? "Application started from the lead"
          : "Application started",
        tone: "info",
      };
    case "UPDATED": {
      const fields = Array.isArray(d.fields) ? (d.fields as string[]) : [];
      return {
        title: "Details updated",
        description: fields.length
          ? `Changed: ${fields.map((f) => DETAIL_FIELD_LABEL[f] ?? f).join(", ")}.`
          : undefined,
      };
    }
    case "SUBMITTED": {
      const count =
        typeof d.documents_for_review === "number" ? d.documents_for_review : 0;
      return {
        title:
          d.from === "CORRECTION_REQUIRED"
            ? "Resubmitted"
            : "Submitted for review",
        description:
          count > 0
            ? `${count} document${count === 1 ? "" : "s"} sent for verification.`
            : undefined,
        tone: "info",
      };
    }
    case "STATUS_CHANGED":
      return {
        title: `Moved from ${status(d.from)} to ${status(d.to)}`,
        description: text(d.reason) ? `Reason: ${text(d.reason)}` : undefined,
        tone:
          d.to === "APPROVED"
            ? "success"
            : d.to === "REJECTED"
              ? "error"
              : d.to === "CORRECTION_REQUIRED" || d.to === "NOT_ELIGIBLE"
                ? "warning"
                : "neutral",
      };
    case "DOCUMENT_UPLOADED":
      return {
        title: d.replaced
          ? `${documentType(d.document_type)} replaced`
          : `${documentType(d.document_type)} uploaded`,
      };
    case "DOCUMENT_VERIFIED":
      return {
        title: `${documentType(d.document_type)} verified`,
        tone: "success",
      };
    case "DOCUMENT_REJECTED":
      return {
        title: `${documentType(d.document_type)} rejected`,
        description: text(d.reason) ? `Reason: ${text(d.reason)}` : undefined,
        tone: "error",
      };
    case "ADMITTED":
      return {
        title: "Admission approved",
        description: [
          text(d.admission_number)
            ? `Admission ${text(d.admission_number)}`
            : null,
          text(d.student_number)
            ? `${d.student_created ? "new student" : "linked to student"} ${text(d.student_number)}`
            : null,
        ]
          .filter(Boolean)
          .join(" · "),
        tone: "success",
      };
    default:
      return { title: "Application updated" };
  }
}

export function ApplicationActivity({
  activities,
}: {
  activities: ApplicationActivityWire[];
}) {
  return (
    <ActivityFeed
      activities={activities}
      describe={describeApplicationActivity}
      label="Application history"
    />
  );
}
