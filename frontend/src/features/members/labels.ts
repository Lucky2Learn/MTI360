import type { Tone } from "@/design-system/components";
import type {
  MembershipStatus,
  MemberWire,
  TenantRoleWire,
} from "@/lib/api/tenant-admin";

// Tenant Users copy and helpers (02-C; ADMIN-05/06 over the T01-08 API).
// Display only: the API authorizes every read and action again.

export const MEMBERS_PATH = "/app/administration/users";
export const memberPath = (id: string) => `${MEMBERS_PATH}/${id}`;

export const MEMBER_READ = "member.read";
export const MEMBER_INVITE = "member.invite";
export const MEMBER_UPDATE = "member.update";
export const MEMBER_SUSPEND = "member.suspend";
export const MEMBER_REVOKE = "member.revoke";
export const ROLE_ASSIGN = "role.assign";
export const ROLE_READ = "role.read";
export const CAMPUS_READ = "campus.read";

export const STATUS_LABEL: Record<MembershipStatus, string> = {
  INVITED: "Invited",
  ACTIVE: "Active",
  SUSPENDED: "Suspended",
  REVOKED: "Removed",
};

export const STATUS_TONE: Record<MembershipStatus, Tone> = {
  INVITED: "info",
  ACTIVE: "success",
  SUSPENDED: "warning",
  REVOKED: "neutral",
};

export const STATUS_DESCRIPTION: Record<MembershipStatus, string> = {
  INVITED: "Hasn't accepted the invitation yet.",
  ACTIVE: "Can sign in to your institute.",
  SUSPENDED: "Can't sign in to your institute until reinstated.",
  REVOKED: "No longer has access. Re-invite to restore it.",
};

/**
 * The signed-in person's own membership, to hide actions the API refuses on
 * oneself (D8-4). UX only: one membership per person per institute, and the
 * API refuses self-actions regardless.
 */
export function isOwnMembership(
  member: Pick<MemberWire, "user">,
  sessionEmail: string,
): boolean {
  return member.user.email.toLowerCase() === sessionEmail.toLowerCase();
}

/**
 * The no-escalation rule as a hint (ADR-0011 §5): a role the caller can't
 * grant because it holds permissions the caller doesn't. The API decides.
 */
export function grantable(
  role: Pick<TenantRoleWire, "permissions">,
  permissions: ReadonlySet<string>,
): boolean {
  return role.permissions.every((code) => permissions.has(code));
}

/**
 * ADR-0023: an Institute owner always has access to all campuses (the API
 * refuses otherwise with `owner_requires_all_campuses`).
 */
export const OWNER_SCOPE_CODE = "owner_requires_all_campuses";
export const OWNER_SCOPE_NOTE =
  "Institute owners always have access to all campuses, so they can manage the whole institute.";
export const OWNER_SCOPE_ERROR =
  "An Institute owner needs access to all campuses. Choose All campuses.";
export const OWNER_ROLE_NEEDS_ALL =
  "Institute owner can only be given to a member with access to all campuses. Change their campus access first.";

export function campusAccessLabel(
  member: Pick<MemberWire, "campus_scope" | "campus_ids">,
): string {
  if (member.campus_scope === "ALL") return "All campuses";
  const count = member.campus_ids.length;
  return `${count} ${count === 1 ? "campus" : "campuses"}`;
}
