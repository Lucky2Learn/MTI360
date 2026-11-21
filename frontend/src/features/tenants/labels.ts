import type { Tone } from "@/design-system/components";
import type { TenantOwnerWire, TenantStatus } from "@/lib/api/platform-tenants";

// Platform Tenants copy (PLAT-04 list, PLAT-05 detail, PLAT-06 create).
// Display only: the platform API authorizes every request.

export const TENANTS_PATH = "/platform/tenants";
export const NEW_TENANT_PATH = `${TENANTS_PATH}/new`;
export const TENANT_READ = "tenant.read";
export const TENANT_CREATE = "tenant.create";
export const TENANT_SUSPEND = "tenant.suspend";
export const TENANT_REACTIVATE = "tenant.reactivate";

export const tenantPath = (id: string) => `${TENANTS_PATH}/${id}`;

/**
 * Statuses the API suspends from (tenants/domain.py, D15). Only decides which
 * button is offered; the API refuses any other status change with 409.
 */
export const SUSPENDABLE: ReadonlySet<TenantStatus> = new Set([
  "TRIAL",
  "ACTIVE",
  "PAST_DUE",
]);

/** The lifecycle (CLAUDE.md §12), in order. */
export const TENANT_STATUSES: readonly TenantStatus[] = [
  "PROSPECT",
  "TRIAL",
  "PROVISIONING",
  "ACTIVE",
  "PAST_DUE",
  "SUSPENDED",
  "CANCELLED",
  "DEACTIVATED",
];

export const STATUS_LABEL: Record<TenantStatus, string> = {
  PROSPECT: "Prospect",
  TRIAL: "Trial",
  PROVISIONING: "Provisioning",
  ACTIVE: "Active",
  PAST_DUE: "Past due",
  SUSPENDED: "Suspended",
  CANCELLED: "Cancelled",
  DEACTIVATED: "Deactivated",
};

export const STATUS_TONE: Record<TenantStatus, Tone> = {
  PROSPECT: "neutral",
  TRIAL: "info",
  PROVISIONING: "info",
  ACTIVE: "success",
  PAST_DUE: "warning",
  SUSPENDED: "error",
  CANCELLED: "neutral",
  DEACTIVATED: "neutral",
};

export const OWNER_STATUS_LABEL: Record<TenantOwnerWire["status"], string> = {
  INVITED: "Invitation sent",
  ACTIVE: "Joined",
  SUSPENDED: "Suspended",
  REVOKED: "Removed",
};
