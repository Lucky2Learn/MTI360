"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import {
  Alert,
  Button,
  Card,
  CardBody,
  CardHeader,
  Form,
  Textarea,
  toast,
} from "@/design-system/components";
import type { ActivityWire, LeadStatus } from "@/lib/api/admissions";
import { formFeedback, type FormFeedback } from "@/lib/authz/action-feedback";
import { PermissionGate } from "@/lib/authz/PermissionGate";
import { useTenantSession } from "@/lib/session/SessionProvider";

import {
  ActivityFeed,
  type ActivityDescription,
} from "../activity/ActivityFeed";
import { formatDateTime } from "../shared/format";

import {
  FIELD_LABEL,
  FOLLOW_UP_KIND_LABEL,
  LEAD_UPDATE,
  STATUS_LABEL,
} from "./labels";

// The lead's history (Phase 02-1; blueprint §12): append-only notes and the
// recorded events, newest first. Notes are plain text (no HTML, no Markdown)
// and cannot be edited or deleted. Names come resolved from the server.

const text = (value: unknown): string | null =>
  typeof value === "string" && value ? value : null;
const status = (value: unknown): string =>
  STATUS_LABEL[value as LeadStatus] ?? "another status";
const kind = (value: unknown): string =>
  FOLLOW_UP_KIND_LABEL[value as keyof typeof FOLLOW_UP_KIND_LABEL] ??
  "Follow-up";

export function describeLeadActivity(
  activity: ActivityWire,
): ActivityDescription {
  const d = activity.details;
  switch (activity.kind) {
    case "CREATED": {
      const count =
        typeof d.possible_duplicates === "number" ? d.possible_duplicates : 0;
      return {
        title: "Lead created",
        description:
          count > 0
            ? `Created despite ${count} possible duplicate${count === 1 ? "" : "s"}.`
            : undefined,
        tone: "info",
      };
    }
    case "UPDATED": {
      const fields = Array.isArray(d.fields) ? (d.fields as string[]) : [];
      return {
        title: "Details updated",
        description: fields.length
          ? `Changed: ${fields.map((f) => FIELD_LABEL[f] ?? f).join(", ")}.`
          : undefined,
      };
    }
    case "STATUS_CHANGED":
      return {
        title: `Moved from ${status(d.from)} to ${status(d.to)}`,
        description: text(d.reason) ? `Reason: ${text(d.reason)}` : undefined,
        tone:
          d.to === "LOST"
            ? "error"
            : d.to === "INTERESTED"
              ? "success"
              : "neutral",
      };
    case "ASSIGNED": {
      const owner =
        text(d.owner_to_name) ?? (d.owner_to ? "a team member" : "nobody");
      const campus =
        text(d.campus_to_name) ?? (d.campus_to ? "a campus" : "institute-wide");
      return {
        title: "Assignment changed",
        description: `Owner: ${owner}. Campus: ${campus}.`,
      };
    }
    case "FOLLOW_UP_SCHEDULED":
      return {
        title: d.rescheduled
          ? `${kind(d.follow_up_kind)} rescheduled`
          : `${kind(d.follow_up_kind)} scheduled`,
        description: text(d.due_at)
          ? `Due ${formatDateTime(text(d.due_at) ?? "")}`
          : undefined,
      };
    case "FOLLOW_UP_COMPLETED":
      return { title: `${kind(d.follow_up_kind)} done`, tone: "success" };
    case "FOLLOW_UP_CANCELLED":
      return { title: `${kind(d.follow_up_kind)} cancelled` };
    case "NOTE":
      return { title: "Note" };
    case "APPLICATION_STARTED":
      return {
        title: "Application started",
        description: text(d.application_number) ?? undefined,
        tone: "success",
      };
  }
}

function NoteForm({ leadId }: { leadId: string }) {
  const router = useRouter();
  const { request } = useTenantSession();
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<FormFeedback | null>(null);
  const [pending, setPending] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (pending) return;
    if (!body.trim()) {
      setError("Write a note.");
      return;
    }
    setPending(true);
    setFeedback(null);
    try {
      await request(`/leads/${leadId}/notes`, {
        method: "POST",
        body: { body },
      });
      setBody("");
      toast.success("Note added");
      router.refresh();
    } catch (failure) {
      setFeedback(
        formFeedback(failure) ?? {
          tone: "error",
          title: "The note wasn't saved",
        },
      );
    } finally {
      setPending(false);
    }
  };

  return (
    <Form
      aria-label="Add a note"
      validationBehavior="aria"
      onSubmit={(event) => void submit(event)}
    >
      {feedback && (
        <Alert tone={feedback.tone} title={feedback.title}>
          {feedback.body}
        </Alert>
      )}
      <Textarea
        label="Add a note"
        value={body}
        onChange={(value) => {
          setBody(value);
          setError(null);
        }}
        rows={3}
        maxLength={4000}
        showCount
        description="Notes are kept in the history and can't be edited later."
        isInvalid={Boolean(error)}
        errorMessage={error ?? undefined}
      />
      <div className="flex justify-end">
        <Button type="submit" isPending={pending}>
          Add note
        </Button>
      </div>
    </Form>
  );
}

export function LeadActivity({
  leadId,
  activities,
  total,
}: {
  leadId: string;
  activities: ActivityWire[];
  total: number;
}) {
  return (
    <Card as="section">
      <CardHeader
        title="Activity"
        titleAs="h2"
        description={
          total > activities.length
            ? `Showing the latest ${activities.length} of ${total} entries.`
            : undefined
        }
      />
      <CardBody>
        <div className="flex flex-col gap-6">
          <PermissionGate permission={LEAD_UPDATE}>
            <NoteForm leadId={leadId} />
          </PermissionGate>
          {activities.length === 0 ? (
            <p className="text-body-sm text-text-secondary">No activity yet.</p>
          ) : (
            <ActivityFeed
              activities={activities}
              describe={describeLeadActivity}
              label="Lead history"
            />
          )}
        </div>
      </CardBody>
    </Card>
  );
}
