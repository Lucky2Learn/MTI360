"use client";

import { useState } from "react";

import { Button } from "@/design-system/components";
import { EditIcon } from "@/design-system/icons";
import type { LeadWire } from "@/lib/api/admissions";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { AssignLeadDialog } from "./AssignLeadDialog";
import { LEAD_ASSIGN, LEAD_UPDATE, leadPath } from "./labels";
import { LeadStatusDialog } from "./LeadStatusDialog";

// GROW-09 header actions (Phase 02-1; blueprint §21): Edit and Change status
// (lead.update), Assign (lead.assign). Hidden without the permission (UX
// only); the API refuses regardless. "Change status" is offered only when
// the server lists a possible move (none for APPLICATION / ADMITTED in 02-1).

export function LeadDetailActions({ lead }: { lead: LeadWire }) {
  const { can } = useTenantSession();
  const [dialog, setDialog] = useState<"move" | "assign" | null>(null);
  const close = (open: boolean) => !open && setDialog(null);
  return (
    <>
      {can(LEAD_UPDATE) && (
        <Button
          variant="secondary"
          iconStart={EditIcon}
          href={`${leadPath(lead.id)}/edit`}
        >
          Edit
        </Button>
      )}
      {can(LEAD_ASSIGN) && (
        <Button variant="secondary" onPress={() => setDialog("assign")}>
          Assign
        </Button>
      )}
      {can(LEAD_UPDATE) && lead.transitions.length > 0 && (
        <Button onPress={() => setDialog("move")}>Change status</Button>
      )}
      {dialog === "move" && (
        <LeadStatusDialog lead={lead} isOpen onOpenChange={close} />
      )}
      {dialog === "assign" && (
        <AssignLeadDialog lead={lead} isOpen onOpenChange={close} />
      )}
    </>
  );
}
