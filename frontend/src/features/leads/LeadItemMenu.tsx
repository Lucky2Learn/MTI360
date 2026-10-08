"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import {
  DropdownMenu,
  IconButton,
  type MenuEntry,
} from "@/design-system/components";
import { MoreIcon } from "@/design-system/icons";
import type { LeadListItemWire } from "@/lib/api/admissions";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { AssignLeadDialog } from "./AssignLeadDialog";
import { LEAD_ASSIGN, LEAD_UPDATE, leadPath } from "./labels";
import { LeadStatusDialog } from "./LeadStatusDialog";

// The per-row (list) and per-card (board) menu: Open, Move to… (lead.update,
// only when the server allows a move) and Assign… (lead.assign). Keyboard,
// screen-reader and touch friendly; the board's only way to move a card
// (no drag-and-drop in 02-1, blueprint §22).

export function LeadItemMenu({ lead }: { lead: LeadListItemWire }) {
  const router = useRouter();
  const { can } = useTenantSession();
  const [dialog, setDialog] = useState<"move" | "assign" | null>(null);

  const items: MenuEntry[] = [
    { id: "open", label: "Open lead" },
    ...(can(LEAD_UPDATE) && lead.transitions.length > 0
      ? [{ id: "move", label: "Move to…" }]
      : []),
    ...(can(LEAD_ASSIGN) ? [{ id: "assign", label: "Assign…" }] : []),
  ];

  return (
    <>
      <DropdownMenu
        trigger={
          <IconButton label={`Actions for ${lead.full_name}`} icon={MoreIcon} />
        }
        items={items}
        onAction={(id) => {
          if (id === "open") router.push(leadPath(lead.id));
          else setDialog(id as "move" | "assign");
        }}
      />
      {dialog === "move" && (
        <LeadStatusDialog
          lead={lead}
          isOpen
          onOpenChange={(open) => !open && setDialog(null)}
        />
      )}
      {dialog === "assign" && (
        <AssignLeadDialog
          lead={lead}
          isOpen
          onOpenChange={(open) => !open && setDialog(null)}
        />
      )}
    </>
  );
}
