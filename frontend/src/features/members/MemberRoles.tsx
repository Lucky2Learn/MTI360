"use client";

import { useState } from "react";

import {
  Alert,
  AlertDialog,
  Button,
  Card,
  CardBody,
  CardHeader,
  IconButton,
  Select,
} from "@/design-system/components";
import { DeleteIcon } from "@/design-system/icons";
import type {
  MemberRoleWire,
  MemberWire,
  TenantRoleWire,
} from "@/lib/api/tenant-admin";
import type { FormFeedback } from "@/lib/authz/action-feedback";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { rolePath } from "../roles/labels";
import { RecordLink } from "../shared/RecordLink";

import {
  grantable,
  isOwnMembership,
  OWNER_ROLE_NEEDS_ALL,
  OWNER_SCOPE_CODE,
  ROLE_ASSIGN,
  ROLE_READ,
} from "./labels";
import { toastFeedback, useMemberMutation } from "./mutations";

// ADMIN-06 roles (02-C; POST / DELETE /members/{id}/roles, role.assign).
// Adding is offered from the institute's roles (GET /roles, role.read)
// that the member doesn't hold and the caller could grant (no escalation,
// as a hint). Removing is never offered on one's own membership (D8-4). The
// API decides both: 409 (already held; the last active owner's owner role)
// and 403 (own membership; access the caller lacks) never show success. A
// held role links to its ADMIN-07 page with role.read. The Institute owner
// role is not offered to a campus-limited member, and the API's 422 for it
// is explained (ADR-0023).

export function MemberRoles({
  member,
  roles,
}: {
  member: MemberWire;
  /** The institute's roles; null when they can't be read (no role.read or a failed read). */
  roles: TenantRoleWire[] | null;
}) {
  const { session, can } = useTenantSession();
  const mutate = useMemberMutation();
  const own = isOwnMembership(member, session.user.email);
  const canAssign = can(ROLE_ASSIGN);
  const canReadRoles = can(ROLE_READ);
  const [choice, setChoice] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [feedback, setFeedback] = useState<FormFeedback | null>(null);
  const [removing, setRemoving] = useState<MemberRoleWire | null>(null);
  const [pendingRemove, setPendingRemove] = useState(false);

  const held = new Set(member.roles.map((role) => role.id));
  const candidates = (roles ?? []).filter(
    (role) => !held.has(role.id) && grantable(role, session.permissions),
  );
  // ADR-0023: the owner role is never offered to a campus-limited member.
  const limited = member.campus_scope === "SELECTED";
  const addable = candidates.filter((role) => !(limited && role.is_owner));
  const ownerWithheld = addable.length < candidates.length;

  const add = async () => {
    if (!choice || adding) return;
    const role = addable.find((item) => item.id === choice);
    setAdding(true);
    setFeedback(null);
    const outcome = await mutate({
      path: `/members/${member.id}/roles`,
      body: { role_id: choice },
      success: `${role?.name ?? "Role"} added to ${member.user.display_name}.`,
      conflict:
        "The role wasn't added. The member may already have it. The latest details are shown.",
    });
    setAdding(false);
    if (outcome.kind === "done") setChoice(null);
    else if (outcome.kind === "feedback") setFeedback(outcome.feedback);
    else
      setFeedback({
        tone: "error",
        title: "The role wasn't added",
        body:
          outcome.fields.role_id === OWNER_SCOPE_CODE
            ? OWNER_ROLE_NEEDS_ALL
            : "This role can't be given to this member.",
      });
  };

  const remove = async (role: MemberRoleWire) => {
    setPendingRemove(true);
    const outcome = await mutate({
      path: `/members/${member.id}/roles/${role.id}`,
      method: "DELETE",
      success: `${role.name} removed from ${member.user.display_name}.`,
      conflict:
        "The role wasn't removed. Your institute must keep at least one active owner, or the roles changed in the meantime. The latest details are shown.",
    });
    setPendingRemove(false);
    setRemoving(null);
    if (outcome.kind === "feedback") toastFeedback(outcome.feedback);
  };

  return (
    <Card as="section">
      <CardHeader
        title="Roles"
        titleAs="h2"
        description="What this member can do in your institute."
      />
      <CardBody>
        <div className="flex flex-col gap-4">
          {member.roles.length === 0 ? (
            <p className="text-body-sm text-text-secondary">
              No roles yet. Without a role, this member can sign in but
              can&apos;t use any section.
            </p>
          ) : (
            <ul className="flex flex-col divide-y divide-border-subtle">
              {member.roles.map((role) => (
                <li
                  key={role.id}
                  className="flex min-h-control-lg items-center justify-between gap-3 py-2"
                >
                  <span className="flex min-w-0 flex-col">
                    <span className="text-body-sm font-medium break-words text-text-primary">
                      {canReadRoles ? (
                        <RecordLink href={rolePath(role.id)}>
                          {role.name}
                        </RecordLink>
                      ) : (
                        role.name
                      )}
                    </span>
                    <span className="text-caption text-text-secondary">
                      {role.is_system ? "System role" : "Custom role"}
                    </span>
                  </span>
                  {canAssign && !own && (
                    <IconButton
                      label={`Remove the ${role.name} role`}
                      icon={DeleteIcon}
                      onPress={() => setRemoving(role)}
                    />
                  )}
                </li>
              ))}
            </ul>
          )}
          {canAssign && own && (
            <p className="text-caption text-text-secondary">
              You can&apos;t remove your own roles. Ask another administrator.
            </p>
          )}
          {canAssign && roles === null && (
            <p className="text-caption text-text-secondary">
              The institute&apos;s roles couldn&apos;t be loaded, so roles
              can&apos;t be added right now.
            </p>
          )}
          {canAssign && roles !== null && (
            <div className="flex flex-col gap-3">
              {feedback && (
                <Alert tone={feedback.tone} title={feedback.title}>
                  {feedback.body}
                </Alert>
              )}
              {ownerWithheld && (
                <p className="text-caption text-text-secondary">
                  {OWNER_ROLE_NEEDS_ALL}
                </p>
              )}
              {addable.length === 0 ? (
                ownerWithheld ? null : (
                  <p className="text-caption text-text-secondary">
                    Every role you can give is already assigned.
                  </p>
                )
              ) : (
                <div className="flex flex-col gap-2 tablet:flex-row tablet:items-end">
                  <div className="min-w-0 tablet:flex-1">
                    <Select
                      label="Add a role"
                      placeholder="Choose a role"
                      options={addable.map((role) => ({
                        id: role.id,
                        label: role.name,
                      }))}
                      value={choice}
                      onChange={(value) => {
                        setChoice(value);
                        setFeedback(null);
                      }}
                      isDisabled={adding}
                    />
                  </div>
                  <Button
                    variant="secondary"
                    onPress={() => void add()}
                    isPending={adding}
                    isDisabled={!choice}
                  >
                    Add role
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>
      </CardBody>
      {removing && (
        <AlertDialog
          isOpen
          onOpenChange={(open) => !open && !pendingRemove && setRemoving(null)}
          title={`Remove the ${removing.name} role from ${member.user.display_name}?`}
          description="They lose what this role allows from their next action. Their other roles are kept."
          confirmLabel="Remove role"
          tone="destructive"
          isPending={pendingRemove}
          onConfirm={() => void remove(removing)}
        />
      )}
    </Card>
  );
}
