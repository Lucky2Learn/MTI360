"use client";

import {
  Badge,
  DataTable,
  type DataTableColumn,
} from "@/design-system/components";
import { LockIcon } from "@/design-system/icons";
import type { TenantRoleWire } from "@/lib/api/tenant-admin";

import { RecordLink } from "../shared/RecordLink";

import { countLabel, roleKindLabel, rolePath } from "./labels";

// ADMIN-07 Roles (02-C; GET /roles, role.read), read-only: the institute's
// roles in the API's order (system roles first, then custom roles by name).
// The API returns every role at once, so there is no paging or filtering.

export function RoleKindBadge({
  role,
}: {
  role: Pick<TenantRoleWire, "is_system">;
}) {
  return (
    <Badge tone="neutral" icon={role.is_system ? LockIcon : false}>
      {roleKindLabel(role)}
    </Badge>
  );
}

export function RoleList({ roles }: { roles: TenantRoleWire[] }) {
  const columns: DataTableColumn<TenantRoleWire>[] = [
    {
      id: "name",
      header: "Role",
      isRowHeader: true,
      cell: (role) => (
        <span className="flex min-w-0 flex-col gap-0.5">
          <RecordLink href={rolePath(role.id)}>{role.name}</RecordLink>
          {role.description && (
            <span className="text-caption break-words text-text-secondary">
              {role.description}
            </span>
          )}
        </span>
      ),
    },
    {
      id: "type",
      header: "Type",
      cell: (role) => <RoleKindBadge role={role} />,
    },
    {
      id: "members",
      header: "Members",
      cell: (role) => countLabel(role.member_count, "member", "members"),
    },
    {
      id: "permissions",
      header: "Permissions",
      visibleFrom: "tablet",
      cell: (role) =>
        countLabel(role.permissions.length, "permission", "permissions"),
    },
  ];

  return (
    <DataTable
      label="Roles"
      columns={columns}
      rows={roles}
      getRowId={(role) => role.id}
      getRowLabel={(role) => role.name}
      mobileLayout="cards"
      emptyState={{
        title: "No roles yet",
        description:
          "Roles appear here once they're set up for your institute.",
      }}
    />
  );
}
