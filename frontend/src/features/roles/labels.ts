import type {
  TenantPermissionWire,
  TenantRoleWire,
} from "@/lib/api/tenant-admin";

// Tenant Roles & Permissions copy and helpers (02-C; ADMIN-07 over the T01-08
// API, read-only). Display only: the API authorizes every read again. Labels
// come from the API: a permission's description, its module and its scope.

export const ROLES_PATH = "/app/administration/roles";
export const rolePath = (id: string) => `${ROLES_PATH}/${id}`;

export const roleKindLabel = (role: Pick<TenantRoleWire, "is_system">) =>
  role.is_system ? "System role" : "Custom role";

export const roleKindDescription = (role: Pick<TenantRoleWire, "is_system">) =>
  role.is_system
    ? "Defined by MTI 360. Its permissions can't be changed."
    : "Created by your institute.";

export const SCOPE_LABEL: Record<TenantPermissionWire["scope"], string> = {
  tenant: "Institute-wide",
  campus: "Per campus",
};

export const countLabel = (count: number, one: string, many: string) =>
  `${count} ${count === 1 ? one : many}`;

/** The API's module slug as a heading: "platform_identity" → "Platform identity". */
export function moduleLabel(module: string): string {
  const words = module.replace(/[_-]+/g, " ").trim();
  return words ? words.charAt(0).toUpperCase() + words.slice(1) : "Other";
}

export type PermissionGroup = {
  module: string;
  label: string;
  permissions: (TenantPermissionWire & { granted: boolean })[];
  granted: number;
};

/**
 * The catalogue grouped by module (groups by label, permissions in catalogue
 * order), each permission marked granted or not for this role. `unlisted` is
 * what the role holds that the catalogue doesn't describe, shown by code.
 */
export function groupPermissions(
  catalogue: TenantPermissionWire[],
  held: readonly string[],
): { groups: PermissionGroup[]; unlisted: string[] } {
  const granted = new Set(held);
  const groups = new Map<string, PermissionGroup>();
  for (const permission of catalogue) {
    let group = groups.get(permission.module);
    if (!group) {
      group = {
        module: permission.module,
        label: moduleLabel(permission.module),
        permissions: [],
        granted: 0,
      };
      groups.set(permission.module, group);
    }
    const isGranted = granted.has(permission.code);
    group.permissions.push({ ...permission, granted: isGranted });
    if (isGranted) group.granted += 1;
  }
  const known = new Set(catalogue.map((permission) => permission.code));
  return {
    groups: [...groups.values()].sort((a, b) => a.label.localeCompare(b.label)),
    unlisted: held.filter((code) => !known.has(code)),
  };
}
