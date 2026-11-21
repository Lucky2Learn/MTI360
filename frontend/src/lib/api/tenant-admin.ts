// Tenant administration wire types (T01-08 API; ADMIN-05/06 Users). Mirrors
// backend/app/modules/identity/members_schemas.py, access/schemas.py and
// institute/router.py field for field, with only what the UI reads. A
// response never contains a token or a credential; a member's user block is
// their name and email only.

export type MembershipStatus = "INVITED" | "ACTIVE" | "SUSPENDED" | "REVOKED";

export type CampusScope = "ALL" | "SELECTED";

/** `MemberRoleOut`. `is_owner`: the Institute owner system role (ADR-0023). */
export type MemberRoleWire = {
  id: string;
  name: string;
  is_system: boolean;
  is_owner: boolean;
};

/** `MemberOut`: GET /members, GET /members/{id} and every member action. */
export type MemberWire = {
  id: string;
  user: { display_name: string; email: string };
  status: MembershipStatus;
  campus_scope: CampusScope;
  /** Only for `SELECTED`; empty for `ALL`. */
  campus_ids: string[];
  roles: MemberRoleWire[];
  /** Holds the Institute owner role, so keeps all-campus access (ADR-0023). */
  is_owner: boolean;
  invited_at: string;
  joined_at: string | null;
  version: number;
};

/** `InvitedMemberOut`: POST /members/invitations. */
export type InvitedMemberWire = {
  member: MemberWire;
  account: "new" | "existing";
};

/** `RoleOut`: GET /roles (system roles first, then custom roles by name). */
export type TenantRoleWire = {
  id: string;
  name: string;
  description: string | null;
  is_system: boolean;
  /** The Institute owner system role: needs all-campus access (ADR-0023). */
  is_owner: boolean;
  permissions: string[];
  member_count: number;
  version: number;
};

/**
 * `PermissionOut`: GET /permissions (the tenant catalogue, sorted by code).
 * `module` is the declaring backend module's slug, e.g. "leads".
 */
export type TenantPermissionWire = {
  code: string;
  scope: "tenant" | "campus";
  description: string;
  module: string;
};

/** `CampusOut`: GET /campuses (only the caller's own campuses, D-B1). */
export type TenantCampusWire = {
  id: string;
  name: string;
  code: string;
  created_at: string;
  updated_at: string;
  version: number;
};
