"use client";

import { useState } from "react";

import { Button } from "@/design-system/components";
import { EditIcon } from "@/design-system/icons";
import type { LeadWire } from "@/lib/api/admissions";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { APPLICATION_CREATE, APPLICATIONS_PATH } from "../applications/labels";

import { AssignLeadDialog } from "./AssignLeadDialog";
import { LEAD_ASSIGN, LEAD_UPDATE, leadPath } from "./labels";
import { LeadStatusDialog } from "./LeadStatusDialog";

// GROW-09 header actions (Phase 02-1; blueprint §21): Edit and Change status
// (lead.update), Assign (lead.assign). Hidden without the permission (UX
// only); the API refuses regardless. "Change status" is offered only when
// the server lists a possible move (none for APPLICATION / ADMITTED).
// Phase 02-2: "Start application" (application.create) for an open lead, or
// a progressed one (a second course); a closed lead is reopened first.

const CLOSED = new Set(["NOT_ELIGIBLE", "LOST", "DEFERRED", "DUPLICATE"]);

/** An open or progressed lead can start an application (the API decides again). */
function startable(lead: LeadWire): boolean {
  return !CLOSED.has(lead.status);
}

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
        <Button
          variant={
            can(APPLICATION_CREATE) && startable(lead) ? "secondary" : "primary"
          }
          onPress={() => setDialog("move")}
        >
          Change status
        </Button>
      )}
      {can(APPLICATION_CREATE) && startable(lead) && (
        <Button href={`${APPLICATIONS_PATH}/new?lead=${lead.id}`}>
          Start application
        </Button>
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
