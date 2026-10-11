"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { AlertDialog, Button, toast } from "@/design-system/components";
import { EditIcon } from "@/design-system/icons";
import { ApiError } from "@/lib/api/errors";
import type { FeeStructureStatus, FeeStructureWire } from "@/lib/api/finance";
import { notifyActionError } from "@/lib/authz/action-feedback";
import { PermissionGate } from "@/lib/authz/PermissionGate";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { FEE_STRUCTURE_MANAGE, structurePath } from "./labels";

// FIN-03 fee structure actions (Phase 02-5; ADR-0022): edit and activate a
// draft, archive. Activating archives the course's current active structure
// in the same step (said in the confirmation). Only with fee_structure.manage;
// the server re-checks the status move and the version, and a conflict
// refreshes the page. Nothing changes on screen before the server answers.

type Target = Extract<FeeStructureStatus, "ACTIVE" | "ARCHIVED">;

export function FeeStructureActions({
  structure,
}: {
  structure: FeeStructureWire;
}) {
  const router = useRouter();
  const { request } = useTenantSession();
  const [confirming, setConfirming] = useState<Target | null>(null);
  const [pending, setPending] = useState(false);

  const move = async (to: Target) => {
    setPending(true);
    try {
      await request(`/fee-structures/${structure.id}/status`, {
        method: "POST",
        body: { status: to, version: structure.version },
      });
      toast.success(
        to === "ACTIVE" ? "Fee structure activated" : "Fee structure archived",
      );
    } catch (error) {
      if (error instanceof ApiError && error.code === "CONFLICT") {
        toast.warning(
          "This fee structure changed — the latest version is shown.",
        );
      } else {
        notifyActionError(error, `fee-structure-status:${structure.id}`);
      }
    } finally {
      setPending(false);
      setConfirming(null);
      router.refresh();
    }
  };

  if (structure.status === "ARCHIVED") return null;
  return (
    <PermissionGate permission={FEE_STRUCTURE_MANAGE}>
      {structure.status === "DRAFT" && (
        <>
          <Button
            variant="secondary"
            iconStart={EditIcon}
            href={`${structurePath(structure.id)}/edit`}
          >
            Edit
          </Button>
          <Button onPress={() => setConfirming("ACTIVE")}>Activate</Button>
        </>
      )}
      <Button variant="secondary" onPress={() => setConfirming("ARCHIVED")}>
        Archive
      </Button>
      <AlertDialog
        isOpen={confirming === "ACTIVE"}
        onOpenChange={(open) => setConfirming(open ? "ACTIVE" : null)}
        title={`Activate ${structure.name}?`}
        description={`New fee invoices for ${structure.course.name} will use these fee heads. The course's current active fee structure, if any, is archived. Issued fee invoices don't change, and an active structure can't be edited.`}
        confirmLabel="Activate fee structure"
        isPending={pending}
        onConfirm={() => void move("ACTIVE")}
      />
      <AlertDialog
        isOpen={confirming === "ARCHIVED"}
        onOpenChange={(open) => setConfirming(open ? "ARCHIVED" : null)}
        title={`Archive ${structure.name}?`}
        description={
          structure.status === "ACTIVE"
            ? "No new fee invoices can be issued for this course until another fee structure is activated. Issued fee invoices don't change."
            : "The draft is kept for reference but can't be activated later."
        }
        confirmLabel="Archive fee structure"
        isPending={pending}
        onConfirm={() => void move("ARCHIVED")}
      />
    </PermissionGate>
  );
}
