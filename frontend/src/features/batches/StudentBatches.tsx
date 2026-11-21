import {
  Badge,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
} from "@/design-system/components";
import type { AllocationWire } from "@/lib/api/batches";

import { formatDate } from "../shared/format";
import { RecordLink } from "../shared/RecordLink";

import { PaymentNote } from "./AllocationPanel";
import { batchPath, END_REASON_LABEL } from "./labels";

// ADM-12 Student 360 Batch (Phase 02-6): the current batch of each admission
// and the allocation history — transfers (from/to), withdrawals with their
// reason, and any payment override with its reason and outstanding amount.
// Data: GET /batch-allocations?student_id=… for batch.read holders, within
// the member's campuses. Server-component compatible.

function Line({ allocation }: { allocation: AllocationWire }) {
  const active = allocation.status === "ACTIVE";
  const moved = [
    allocation.transferred_from_batch_code
      ? `from ${allocation.transferred_from_batch_code}`
      : null,
    allocation.transferred_to_batch_code
      ? `to ${allocation.transferred_to_batch_code}`
      : null,
  ].filter(Boolean);
  return (
    <li className="flex min-w-0 flex-col gap-2 border-b border-border-subtle pb-4 last:border-b-0 last:pb-0">
      <span className="flex flex-wrap items-center gap-2 text-body-sm font-medium text-text-primary">
        <RecordLink href={batchPath(allocation.batch.id)}>
          {`${allocation.batch.code} · ${allocation.batch.name}`}
        </RecordLink>
        <Badge
          tone={
            active
              ? "success"
              : allocation.end_reason === "WITHDRAWN"
                ? "warning"
                : "info"
          }
        >
          {active
            ? "Current"
            : allocation.end_reason
              ? END_REASON_LABEL[allocation.end_reason]
              : "Ended"}
        </Badge>
      </span>
      <span className="text-caption text-text-secondary">
        {[
          `${allocation.course.code} · ${allocation.admission_number}`,
          `Allocated ${formatDate(allocation.allocated_at)}${allocation.allocated_by ? ` by ${allocation.allocated_by.display_name}` : ""}`,
          ...moved,
        ].join(" · ")}
      </span>
      {!active && (
        <span className="text-caption break-words text-text-secondary">
          {[
            allocation.ended_at
              ? `Ended ${formatDate(allocation.ended_at)}`
              : null,
            allocation.ended_by
              ? `by ${allocation.ended_by.display_name}`
              : null,
            allocation.end_note ? `“${allocation.end_note}”` : null,
          ]
            .filter(Boolean)
            .join(" · ")}
        </span>
      )}
      <PaymentNote allocation={allocation} />
    </li>
  );
}

export function StudentBatches({
  allocations,
}: {
  allocations: AllocationWire[];
}) {
  return (
    <Card as="section">
      <CardHeader title="Batch" titleAs="h2" />
      <CardBody>
        {allocations.length === 0 ? (
          <EmptyState
            title="Not in a batch"
            description="Allocate this student from a batch of their course. Batches at campuses you don't work with are not shown."
          />
        ) : (
          <ul className="flex flex-col gap-4">
            {allocations.map((allocation) => (
              <Line key={allocation.id} allocation={allocation} />
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}
