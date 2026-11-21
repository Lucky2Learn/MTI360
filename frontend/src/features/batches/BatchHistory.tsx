import type { BatchActivityWire } from "@/lib/api/batches";

import { ActivityFeed } from "../activity/ActivityFeed";

import { describeBatchActivity } from "./labels";

// ACA-06 batch history (Phase 02-6): creation, edits, status changes,
// allocations, transfers and withdrawals, newest first. Server-component
// compatible.

export function BatchHistory({ entries }: { entries: BatchActivityWire[] }) {
  return (
    <ActivityFeed
      activities={entries}
      describe={describeBatchActivity}
      label="Batch history"
    />
  );
}
