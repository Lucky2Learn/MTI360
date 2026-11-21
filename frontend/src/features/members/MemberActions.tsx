"use client";

import { useState } from "react";

import { AlertDialog, Button } from "@/design-system/components";
import type { MembershipStatus, MemberWire } from "@/lib/api/tenant-admin";
import { useTenantSession } from "@/lib/session/SessionProvider";

import {
  isOwnMembership,
  MEMBER_INVITE,
  MEMBER_REVOKE,
  MEMBER_SUSPEND,
} from "./labels";
import { toastFeedback, useMemberMutation } from "./mutations";

// ADMIN-06 status actions (02-C; D8-3 status changes). Each is offered only in
// the statuses the API accepts and with its permission, and never on the
// signed-in person's own membership (D8-4; the API refuses with 403 anyway).
// Every action asks first. A refusal never shows success: 409 (a change in
// the meantime, the last active owner, a disabled account) warns and shows
// the latest data; 403 explains; the API stays authoritative.

type ActionId = "resend" | "reinvite" | "reinstate" | "suspend" | "revoke";

type ActionSpec = {
  label: string;
  permission: string;
  from: MembershipStatus[];
  destructive?: boolean;
  path: (id: string) => `/${string}`;
  versioned: boolean;
  title: (name: string) => string;
  description: (member: MemberWire) => string;
  confirm: string;
  success: (member: MemberWire) => string;
  conflict: string;
};

const ACTIONS: Record<ActionId, ActionSpec> = {
  resend: {
    label: "Resend invitation",
    permission: MEMBER_INVITE,
    from: ["INVITED"],
    path: (id) => `/members/${id}/invitation/resend`,
    versioned: false,
    title: (name) => `Resend the invitation to ${name}?`,
    description: (member) =>
      `A new invitation is emailed to ${member.user.email}. The previous invitation link stops working.`,
    confirm: "Resend invitation",
    success: (member) =>
      `A new invitation is being emailed to ${member.user.email}.`,
    conflict:
      "The invitation wasn't re-sent. The member may have joined in the meantime, or their account is disabled. The latest details are shown.",
  },
  reinvite: {
    label: "Re-invite",
    permission: MEMBER_INVITE,
    from: ["REVOKED"],
    path: (id) => `/members/${id}/reinvite`,
    versioned: true,
    title: (name) => `Re-invite ${name}?`,
    description: (member) =>
      `A new invitation is emailed to ${member.user.email}. Their previous roles are removed: assign roles again after re-inviting. Their campus access is kept.`,
    confirm: "Re-invite",
    success: (member) =>
      `${member.user.display_name} was re-invited. The invitation is being emailed.`,
    conflict:
      "This member wasn't re-invited. Their details changed in the meantime, or their account is disabled. The latest details are shown.",
  },
  reinstate: {
    label: "Reinstate",
    permission: MEMBER_SUSPEND,
    from: ["SUSPENDED"],
    path: (id) => `/members/${id}/reinstate`,
    versioned: true,
    title: (name) => `Reinstate ${name}?`,
    description: () =>
      "They can sign in to your institute again, with their current roles and campus access.",
    confirm: "Reinstate",
    success: (member) => `${member.user.display_name} was reinstated.`,
    conflict:
      "This member wasn't reinstated. Their details changed in the meantime. The latest details are shown.",
  },
  suspend: {
    label: "Suspend",
    permission: MEMBER_SUSPEND,
    from: ["ACTIVE"],
    destructive: true,
    path: (id) => `/members/${id}/suspend`,
    versioned: true,
    title: (name) => `Suspend ${name}?`,
    description: () =>
      "They lose access to your institute from their next action. Their roles and campus access are kept, and you can reinstate them later.",
    confirm: "Suspend member",
    success: (member) => `${member.user.display_name} was suspended.`,
    conflict:
      "This member wasn't suspended. Their details changed in the meantime, or they are your institute's last active owner. The latest details are shown.",
  },
  revoke: {
    label: "Remove from institute",
    permission: MEMBER_REVOKE,
    from: ["INVITED", "ACTIVE", "SUSPENDED"],
    destructive: true,
    path: (id) => `/members/${id}/revoke`,
    versioned: true,
    title: (name) => `Remove ${name} from your institute?`,
    description: () =>
      "They lose access to your institute, and any open invitation stops working. You can re-invite them later.",
    confirm: "Remove member",
    success: (member) =>
      `${member.user.display_name} was removed from your institute.`,
    conflict:
      "This member wasn't removed. Their details changed in the meantime, or they are your institute's last active owner. The latest details are shown.",
  },
};

const ORDER: ActionId[] = [
  "resend",
  "reinvite",
  "reinstate",
  "suspend",
  "revoke",
];

/** The status actions this session may offer for `member` (UX only). */
export function availableActions(
  member: MemberWire,
  can: (code: string) => boolean,
  sessionEmail: string,
): ActionId[] {
  if (isOwnMembership(member, sessionEmail)) return [];
  return ORDER.filter(
    (id) =>
      ACTIONS[id].from.includes(member.status) && can(ACTIONS[id].permission),
  );
}

export function MemberActions({ member }: { member: MemberWire }) {
  const { session, can } = useTenantSession();
  const mutate = useMemberMutation();
  const [confirming, setConfirming] = useState<ActionId | null>(null);
  const [pending, setPending] = useState(false);
  const actions = availableActions(member, can, session.user.email);
  if (actions.length === 0) return null;

  const run = async (id: ActionId) => {
    const spec = ACTIONS[id];
    setPending(true);
    const outcome = await mutate({
      path: spec.path(member.id),
      body: spec.versioned ? { version: member.version } : undefined,
      success: spec.success(member),
      conflict: spec.conflict,
    });
    setPending(false);
    setConfirming(null);
    if (outcome.kind === "feedback") toastFeedback(outcome.feedback);
  };

  const spec = confirming ? ACTIONS[confirming] : null;
  return (
    <>
      {actions.map((id) => (
        <Button key={id} variant="secondary" onPress={() => setConfirming(id)}>
          {ACTIONS[id].label}
        </Button>
      ))}
      {spec && confirming && (
        <AlertDialog
          isOpen
          onOpenChange={(open) => !open && !pending && setConfirming(null)}
          title={spec.title(member.user.display_name)}
          description={spec.description(member)}
          confirmLabel={spec.confirm}
          tone={spec.destructive ? "destructive" : "default"}
          isPending={pending}
          onConfirm={() => void run(confirming)}
        />
      )}
    </>
  );
}
