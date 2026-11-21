import type { ActivityWire, TimelineEntryWire } from "@/lib/api/admissions";

import {
  ActivityFeed,
  type ActivityDescription,
} from "../activity/ActivityFeed";
import { describeApplicationActivity } from "../applications/ApplicationActivity";
import { describeBatchActivity } from "../batches/labels";
import { describeLeadActivity } from "../leads/LeadActivity";

// The Student 360 history (Phase 02-2; ADR-0021 §12): the student's enquiry
// (lead) and application events in one timeline, newest first. The server
// includes lead events only for lead.read holders and application events only
// for application.read holders, each within the member's campuses. Batch
// allocation, transfer and withdrawal (Phase 02-6) for batch.read holders.

function describe(entry: TimelineEntryWire): ActivityDescription {
  if (entry.source === "lead") {
    const described = describeLeadActivity(entry as unknown as ActivityWire);
    return { ...described, title: <>Enquiry: {described.title}</> };
  }
  if (entry.source === "batch") {
    const described = describeBatchActivity(entry);
    return { ...described, title: <>Batch: {described.title}</> };
  }
  const described = describeApplicationActivity(entry);
  return { ...described, title: <>Application: {described.title}</> };
}

export function StudentTimeline({ entries }: { entries: TimelineEntryWire[] }) {
  return (
    <ActivityFeed
      activities={entries}
      describe={describe}
      label="Student history"
    />
  );
}
