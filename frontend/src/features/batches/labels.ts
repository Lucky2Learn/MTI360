import type { Tone } from "@/design-system/components";
import type {
  BatchStatus,
  EndReason,
  InvoiceState,
  PaymentBasis,
} from "@/lib/api/batches";

import { formatPaise } from "../finance/money";

import type { ActivityDescription } from "../activity/ActivityFeed";

// Batches copy (Phase 02-6; ACA-05/06/07). Display only: the server decides.

export const BATCHES_PATH = "/app/academics/batches";
export const BATCH_READ = "batch.read";
export const BATCH_MANAGE = "batch.manage";
export const BATCH_ALLOCATE = "batch.allocate";

export const batchPath = (id: string) => `${BATCHES_PATH}/${id}`;

export const STATUS_LABEL: Record<BatchStatus, string> = {
  OPEN: "Open",
  CLOSED: "Closed",
  CANCELLED: "Cancelled",
};

export const STATUS_TONE: Record<BatchStatus, Tone> = {
  OPEN: "success",
  CLOSED: "neutral",
  CANCELLED: "warning",
};

export const INVOICE_STATE_LABEL: Record<InvoiceState, string> = {
  PAID: "Fees paid",
  PARTIALLY_PAID: "Part paid",
  ISSUED: "Unpaid",
  NO_INVOICE: "No fee invoice",
};

export const INVOICE_STATE_TONE: Record<InvoiceState, Tone> = {
  PAID: "success",
  PARTIALLY_PAID: "warning",
  ISSUED: "warning",
  NO_INVOICE: "error",
};

export const BASIS_LABEL: Record<PaymentBasis, string> = {
  PAID: "Fees paid",
  // Short enough for the two-column mobile card (the details follow it).
  OVERRIDE: "Fee override",
  TRANSFER: "Transferred in",
};

export const BASIS_TONE: Record<PaymentBasis, Tone> = {
  PAID: "success",
  OVERRIDE: "warning",
  TRANSFER: "info",
};

export const END_REASON_LABEL: Record<EndReason, string> = {
  TRANSFERRED: "Transferred out",
  WITHDRAWN: "Withdrawn",
};

/** "18 of 24 seats" and a utilisation percentage (0-100). */
export function seats(batch: { capacity: number; allocated_count: number }): {
  label: string;
  percent: number;
} {
  const percent = Math.min(
    100,
    Math.round((batch.allocated_count / Math.max(batch.capacity, 1)) * 100),
  );
  return {
    label: `${batch.allocated_count} of ${batch.capacity} seats`,
    percent,
  };
}

export function outstandingLabel(minor: number | null): string {
  return minor === null
    ? "No fee invoice"
    : `${formatPaise(minor)} outstanding`;
}

function text(value: unknown): string | null {
  return typeof value === "string" && value ? value : null;
}

/** Batch and Student 360 history entries (`batch_activities`). */
export function describeBatchActivity(activity: {
  kind: string;
  details: Record<string, unknown>;
}): ActivityDescription {
  const d = activity.details;
  const batch = text(d.batch_code);
  switch (activity.kind) {
    case "CREATED":
      return { title: "Batch created", tone: "info" };
    case "UPDATED": {
      const fields = Array.isArray(d.changed_fields)
        ? (d.changed_fields as string[]).map((f) => f.replaceAll("_", " "))
        : [];
      return {
        title: "Batch details updated",
        description: fields.length
          ? `Changed: ${fields.join(", ")}.`
          : undefined,
      };
    }
    case "STATUS_CHANGED": {
      const to = text(d.to) as BatchStatus | null;
      return {
        title: to
          ? `Batch ${STATUS_LABEL[to].toLowerCase()}`
          : "Status changed",
        tone: to ? STATUS_TONE[to] : undefined,
      };
    }
    case "ALLOCATED": {
      const override = d.payment_basis === "OVERRIDE";
      return {
        title: batch ? `Allocated to ${batch}` : "Allocated to the batch",
        description: [
          text(d.admission_number),
          override
            ? `Payment override (${outstandingLabel(
                typeof d.outstanding_minor === "number"
                  ? d.outstanding_minor
                  : null,
              )})`
            : "Fees paid",
        ]
          .filter(Boolean)
          .join(" · "),
        tone: override ? "warning" : "success",
      };
    }
    case "TRANSFERRED_IN":
    case "TRANSFERRED_OUT":
      return {
        title: `Transferred from ${text(d.from_batch_code) ?? "a batch"} to ${
          text(d.to_batch_code) ?? "another batch"
        }`,
        description: text(d.admission_number) ?? undefined,
        tone: "info",
      };
    case "WITHDRAWN":
      return {
        title: batch ? `Withdrawn from ${batch}` : "Withdrawn from the batch",
        description: text(d.admission_number) ?? undefined,
        tone: "warning",
      };
    default:
      return { title: "Batch activity" };
  }
}
