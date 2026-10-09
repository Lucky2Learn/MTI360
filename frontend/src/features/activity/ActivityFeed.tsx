import {
  Timeline,
  type TimelineItem,
  type Tone,
} from "@/design-system/components";

import { formatDateTime } from "../shared/format";

import type { ReactNode } from "react";

// ActivityFeed (Phase 02-1; blueprint §12, §28): a record's user-visible
// history (lead_activities today; application activity and the Student 360
// timeline in 02-2) rendered on the design-system Timeline. The feature
// supplies `describe` (title, detail and tone per activity kind); notes are
// shown as plain text with their line breaks — never as HTML.

export type ActivityDescription = {
  title: ReactNode;
  description?: ReactNode;
  tone?: Tone;
};

/** What the feed needs of an activity row (lead, application or Student 360). */
export type FeedActivity = {
  id: string;
  actor: { display_name: string } | null;
  body?: string | null;
  created_at: string;
};

export type ActivityFeedProps<A extends FeedActivity> = {
  activities: A[];
  describe: (activity: A) => ActivityDescription;
  label: string;
};

export function NoteBody({ body }: { body: string }) {
  return (
    <p className="whitespace-pre-wrap break-words text-body-sm text-text-primary">
      {body}
    </p>
  );
}

export function ActivityFeed<A extends FeedActivity>({
  activities,
  describe,
  label,
}: ActivityFeedProps<A>) {
  const items: TimelineItem[] = activities.map((activity) => {
    const { title, description, tone } = describe(activity);
    return {
      id: activity.id,
      title,
      timestamp: activity.created_at,
      timestampLabel: formatDateTime(activity.created_at),
      actor: activity.actor?.display_name,
      description:
        activity.body !== null && activity.body !== undefined ? (
          <NoteBody body={activity.body} />
        ) : (
          description
        ),
      tone,
    };
  });
  return <Timeline items={items} aria-label={label} />;
}
