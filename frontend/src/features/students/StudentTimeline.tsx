import type { ActivityWire, TimelineEntryWire } from "@/lib/api/admissions";

import {
  ActivityFeed,
  type ActivityDescription,
} from "../activity/ActivityFeed";
import { describeApplicationActivity } from "../applications/ApplicationActivity";
import { describeLeadActivity } from "../leads/LeadActivity";

// The Student 360 history (Phase 02-2; ADR-0021 §12): the student's enquiry
// (lead) and application events in one timeline, newest first. The server
// includes lead events only for lead.read holders and application events only
// for application.read holders, each within the member's campuses.

function describe(entry: TimelineEntryWire): ActivityDescription {
  if (entry.source === "lead") {
    const described = describeLeadActivity(entry as unknown as ActivityWire);
    return { ...described, title: <>Enquiry: {described.title}</> };
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
