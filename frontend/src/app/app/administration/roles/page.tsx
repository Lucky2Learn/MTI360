import { DataListTemplate } from "@/design-system/templates/DataListTemplate";
import { ROLE_READ } from "@/features/members/labels";
import { ROLES_PATH } from "@/features/roles/labels";
import { RoleList } from "@/features/roles/RoleList";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import { tenantApiRead } from "@/lib/api/server-read";
import type { TenantRoleWire } from "@/lib/api/tenant-admin";
import { settle, tenantPageAccess } from "@/lib/session/page-access";
import { SessionSync } from "@/lib/session/SessionProvider";
import { ShellAccessDenied } from "@/shells";

import type { Metadata } from "next";

// ADMIN-07 Roles & Permissions, /app/administration/roles (02-C over the
// T01-08 API, read-only). Gate: ready session → role.read (AUTHZ-01 at this
// URL otherwise) → the role list read on the server with the tenant cookie
// only. The API authorizes the read again and lists the session's institute
// only. Creating, editing and deleting custom roles is future work.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Roles & Permissions · Tenant Application · MTI 360",
};

const BREADCRUMBS = [{ label: "Administration" }, { label: "Roles" }];

export default async function RolesPage() {
  const { session, allowed } = await tenantPageAccess(ROLES_PATH, ROLE_READ);
  if (!allowed) {
    return (
      <>
        <SessionSync session={session} />
        <ShellAccessDenied homeHref="/app" />
      </>
    );
  }
  const result = settle(
    await tenantApiRead<TenantRoleWire[]>("/roles"),
    ROLES_PATH,
  );
  return (
    <>
      <SessionSync session={session} />
      <DataListTemplate
        title="Roles & Permissions"
        description="What each role in your institute allows. A member can hold several roles."
        breadcrumbs={BREADCRUMBS}
      >
        {result.kind === "ok" ? (
          <RoleList roles={result.data} />
        ) : result.kind === "denied" ? (
          <ShellAccessDenied homeHref="/app" />
        ) : (
          <ReadErrorState
            title="Roles couldn't be loaded"
            reference={result.reference}
          />
        )}
      </DataListTemplate>
    </>
  );
}
