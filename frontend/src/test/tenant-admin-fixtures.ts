import type {
  MemberWire,
  TenantCampusWire,
  TenantPermissionWire,
  TenantRoleWire,
} from "@/lib/api/tenant-admin";

import { CAMPUSES } from "./session-fixtures";

// Tenant administration fixtures (02-C; ADMIN-05/06/07). Realistic maritime
// sample data (CLAUDE.md §61); never used by application code. The signed-in
// person of `readySession()` is Ananya Rao, so `member({ id: IDS.self })`
// with her email is "your own membership".

export const MEMBER_IDS = {
  self: "0192a1b2-c3d4-7e5f-8a6b-7c8d9e0f1a01",
  rahul: "0192a1b2-c3d4-7e5f-8a6b-7c8d9e0f1a02",
  priya: "0192a1b2-c3d4-7e5f-8a6b-7c8d9e0f1a03",
  ownerRole: "0192a1b2-c3d4-7e5f-8a6b-7c8d9e0f1b01",
  counsellorRole: "0192a1b2-c3d4-7e5f-8a6b-7c8d9e0f1b02",
  financeRole: "0192a1b2-c3d4-7e5f-8a6b-7c8d9e0f1b03",
  hiddenCampus: "0192a1b2-c3d4-7e5f-8a6b-7c8d9e0f1c09",
} as const;

export const SELF_EMAIL = "ananya.rao@coastal-maritime.example";

/** An institute owner's member-administration permissions (plus leads). */
export const OWNER_PERMISSIONS = [
  "member.read",
  "member.invite",
  "member.update",
  "member.suspend",
  "member.revoke",
  "role.read",
  "role.assign",
  "campus.read",
  "lead.read",
  "lead.create",
];

export function member(overrides: Partial<MemberWire> = {}): MemberWire {
  return {
    id: MEMBER_IDS.rahul,
    user: {
      display_name: "Rahul Menon",
      email: "rahul.menon@coastal-maritime.example",
    },
    status: "ACTIVE",
    campus_scope: "SELECTED",
    campus_ids: [CAMPUSES.kochi.id],
    roles: [
      {
        id: MEMBER_IDS.counsellorRole,
        name: "Counsellor",
        is_system: true,
        is_owner: false,
      },
    ],
    is_owner: false,
    invited_at: "2026-10-01T09:30:00+05:30",
    joined_at: "2026-10-02T11:00:00+05:30",
    version: 3,
    ...overrides,
  };
}

export const selfMember = (overrides: Partial<MemberWire> = {}) =>
  member({
    id: MEMBER_IDS.self,
    user: { display_name: "Ananya Rao", email: SELF_EMAIL },
    campus_scope: "ALL",
    campus_ids: [],
    roles: [
      {
        id: MEMBER_IDS.ownerRole,
        name: "Institute owner",
        is_system: true,
        is_owner: true,
      },
    ],
    is_owner: true,
    ...overrides,
  });

export function role(overrides: Partial<TenantRoleWire> = {}): TenantRoleWire {
  return {
    id: MEMBER_IDS.counsellorRole,
    name: "Counsellor",
    description: "Works leads and applications.",
    is_system: true,
    is_owner: false,
    permissions: ["lead.read", "lead.create"],
    member_count: 4,
    version: 1,
    ...overrides,
  };
}

export const ROLES: TenantRoleWire[] = [
  role({
    id: MEMBER_IDS.ownerRole,
    name: "Institute owner",
    is_owner: true,
    permissions: OWNER_PERMISSIONS,
    member_count: 1,
  }),
  role(),
  role({
    id: MEMBER_IDS.financeRole,
    name: "Finance manager",
    permissions: ["invoice.read", "payment.record"],
    member_count: 1,
  }),
];

/** A slice of GET /permissions: code order, as the API sorts it. */
export const PERMISSION_CATALOGUE: TenantPermissionWire[] = [
  {
    code: "campus.read",
    scope: "campus",
    description: "View campuses",
    module: "institute",
  },
  {
    code: "invoice.read",
    scope: "campus",
    description: "View fee invoices, payments and receipts",
    module: "finance",
  },
  {
    code: "lead.create",
    scope: "campus",
    description: "Add leads",
    module: "leads",
  },
  {
    code: "lead.read",
    scope: "campus",
    description: "View leads and their history",
    module: "leads",
  },
  {
    code: "member.read",
    scope: "tenant",
    description: "View members",
    module: "identity",
  },
  {
    code: "role.read",
    scope: "tenant",
    description: "View roles",
    module: "access",
  },
];

export function campus(
  overrides: Partial<TenantCampusWire> = {},
): TenantCampusWire {
  return {
    ...CAMPUSES.kochi,
    created_at: "2026-09-01T09:00:00+05:30",
    updated_at: "2026-09-01T09:00:00+05:30",
    version: 1,
    ...overrides,
  };
}

export const CAMPUS_LIST: TenantCampusWire[] = [
  campus(),
  campus({ ...CAMPUSES.vizag }),
];
