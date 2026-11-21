"use client";

import { useState } from "react";

import { AlertDialog, Button } from "@/design-system/components";
import { EditIcon } from "@/design-system/icons";
import type { BatchStatus, BatchWire } from "@/lib/api/batches";
import { PermissionGate } from "@/lib/authz/PermissionGate";

import { useFinanceMutation } from "../finance/mutations";
import { ReasonDialog, type ReasonOutcome } from "../finance/ReasonDialog";

import { BATCH_MANAGE, batchPath } from "./labels";

// ACA-06 batch actions (Phase 02-6): edit, close (no new allocations),
// reopen, and cancel (only when nobody is allocated; a reason is kept).
// batch.manage only (UX; the server re-checks the move, the seats and the
// version). A cancelled batch has no actions.

export function BatchActions({ batch }: { batch: BatchWire }) {
  const mutate = useFinanceMutation("batch");
  const [pending, setPending] = useState<BatchStatus | null>(null);
  const [closing, setClosing] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  if (batch.status === "CANCELLED") return null;

  const move = async (status: BatchStatus, done: string, reason?: string) => {
    setPending(status);
    const outcome = await mutate(
      `/batches/${batch.id}/status`,
      { status, reason: reason ?? null, version: batch.version },
      done,
    );
    setPending(null);
    return outcome;
  };

  const cancel = async (reason: string): Promise<ReasonOutcome> => {
    const outcome = await move("CANCELLED", "Batch cancelled", reason);
    if (outcome.kind === "done" || outcome.kind === "stale")
      return { kind: "done" };
    if (outcome.kind === "fields") {
      return outcome.fields.status === "batch_has_allocations"
        ? {
            kind: "feedback",
            feedback: {
              tone: "warning",
              title: "Students are still allocated",
              body: "Withdraw or transfer every allocated student before cancelling this batch.",
            },
          }
        : { kind: "reason", message: "Use at most 500 characters." };
    }
    return { kind: "feedback", feedback: outcome.feedback };
  };

  return (
    <PermissionGate permission={BATCH_MANAGE}>
      <Button
        variant="secondary"
        iconStart={EditIcon}
        href={`${batchPath(batch.id)}/edit`}
      >
        Edit
      </Button>
      {batch.status === "OPEN" ? (
        <Button
          variant="secondary"
          onPress={() => setClosing(true)}
          isPending={pending === "CLOSED"}
        >
          Close batch
        </Button>
      ) : (
        <Button
          onPress={() => void move("OPEN", "Batch reopened")}
          isPending={pending === "OPEN"}
        >
          Reopen batch
        </Button>
      )}
      {batch.allocated_count === 0 && (
        <Button variant="secondary" onPress={() => setCancelling(true)}>
          Cancel batch
        </Button>
      )}
      <AlertDialog
        isOpen={closing}
        onOpenChange={setClosing}
        title={`Close ${batch.code}?`}
        description="No more students can be allocated while the batch is closed. Allocated students stay. You can reopen it later."
        confirmLabel="Close batch"
        isPending={pending === "CLOSED"}
        onConfirm={() =>
          void move("CLOSED", "Batch closed").then(() => setClosing(false))
        }
      />
      <ReasonDialog
        isOpen={cancelling}
        onOpenChange={setCancelling}
        title={`Cancel ${batch.code}?`}
        description="A cancelled batch can't be reopened or changed. Only an empty batch can be cancelled."
        reasonLabel="Reason for cancelling"
        confirmLabel="Cancel batch"
        onSubmit={cancel}
      />
    </PermissionGate>
  );
}
