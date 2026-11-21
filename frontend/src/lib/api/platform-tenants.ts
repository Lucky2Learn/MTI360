// Platform tenant administration wire types (T01-07 API; Platform Tenants
// UI). Mirrors backend/app/modules/tenants/schemas.py. A response never
// contains a token or another member of the tenant: the owner block is the
// primary administrator only.

export type TenantStatus =
  | "PROSPECT"
  | "TRIAL"
  | "PROVISIONING"
  | "ACTIVE"
  | "PAST_DUE"
  | "SUSPENDED"
  | "CANCELLED"
  | "DEACTIVATED";

/** `TenantOut`: GET /platform/tenants (list items). */
export type TenantWire = {
  id: string;
  name: string;
  status: TenantStatus;
  created_at: string;
  updated_at: string;
  version: number;
};

/** `TenantOwnerOut`: `INVITED` until the administrator accepts. */
export type TenantOwnerWire = {
  display_name: string;
  email: string;
  status: "INVITED" | "ACTIVE" | "SUSPENDED" | "REVOKED";
};

/** `TenantDetailOut`: GET /platform/tenants/{id}. */
export type TenantDetailWire = TenantWire & { owner: TenantOwnerWire | null };

/** `ProvisionedTenantOut`: POST /platform/tenants (201). */
export type ProvisionedTenantWire = {
  tenant: TenantDetailWire;
  campus: { id: string; name: string; code: string };
  owner_account: "new" | "existing";
};
