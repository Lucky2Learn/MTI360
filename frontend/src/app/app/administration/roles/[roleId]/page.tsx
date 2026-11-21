import { Alert, Card, CardBody, CardHeader } from "@/design-system/components";
import { DetailTemplate } from "@/design-system/templates/DetailTemplate";
import {
  MEMBER_READ,
  MEMBERS_PATH,
  ROLE_READ,
} from "@/features/members/labels";
import {
  countLabel,
  roleKindDescription,
  rolePath,
  ROLES_PATH,
} from "@/features/roles/labels";
import { RoleKindBadge } from "@/features/roles/RoleList";
import { RolePermissions } from "@/features/roles/RolePermissions";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import { RecordLink } from "@/features/shared/RecordLink";
import { tenantApiRead } from "@/lib/api/server-read";
import type {
  TenantPermissionWire,
  TenantRoleWire,
} from "@/lib/api/tenant-admin";
import { can } from "@/lib/authz/requirements";
import {
  requireRecordId,
  settle,
  tenantPageAccess,
} from "@/lib/session/page-access";
import { SessionSync } from "@/lib/session/SessionProvider";
import { PageContainer, ShellAccessDenied } from "@/shells";

import type { Metadata } from "next";
import type { ReactNode } from "react";

// ADMIN-07 Role detail, /app/administration/roles/[roleId] (02-C over the
// T01-08 API, read-only). The role and the permission catalogue (both
// role.read) are read in parallel on the server. Another institute's role is
// RESOURCE-02 (the API answers 404). A failed catalogue read still shows the
// role, with its permissions by code.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Role · Tenant Application · MTI 360",
};

type Props = { params: Promise<{ roleId: string }> };

function Term({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <dt className="text-body-sm text-text-secondary">{term}</dt>
      <dd className="min-w-0 text-body-sm break-words text-text-primary">
        {children}
      </dd>
    </div>
  );
}

function Summary({
  role,
  canReadMembers,
}: {
  role: TenantRoleWire;
  canReadMembers: boolean;
}) {
  return (
    <Card as="section">
      <CardHeader title="Summary" titleAs="h2" />
      <CardBody>
        <dl className="flex flex-col gap-4">
          <Term term="Type">{roleKindDescription(role)}</Term>
          <Term term="Members">
            <span className="flex flex-col gap-1">
              {countLabel(role.member_count, "member", "members")}
              {canReadMembers && (
                <span>
                  <RecordLink href={MEMBERS_PATH}>View users</RecordLink>
                </span>
              )}
            </span>
          </Term>
          <Term term="Permissions">
            {countLabel(role.permissions.length, "permission", "permissions")}
          </Term>
        </dl>
      </CardBody>
    </Card>
  );
}

export default async function RoleDetailPage({ params }: Props) {
  const id = requireRecordId((await params).roleId);
  const path = rolePath(id);
  const { session, allowed } = await tenantPageAccess(path, ROLE_READ);
  if (!allowed) {
    return (
      <>
        <SessionSync session={session} />
        <ShellAccessDenied homeHref="/app" />
      </>
    );
  }
  const [roleRead, catalogueRead] = await Promise.all([
    tenantApiRead<TenantRoleWire>(`/roles/${id}`),
    tenantApiRead<TenantPermissionWire[]>("/permissions"),
  ]);
  const role = settle(roleRead, path);
  if (role.kind !== "ok") {
    return (
      <>
        <SessionSync session={session} />
        {role.kind === "denied" ? (
          <ShellAccessDenied homeHref="/app" />
        ) : (
          <PageContainer>
            <ReadErrorState
              title="This role couldn't be loaded"
              reference={role.reference}
            />
          </PageContainer>
        )}
      </>
    );
  }
  const data = role.data;

  return (
    <>
      <SessionSync session={session} />
      <DetailTemplate
        title={data.name}
        description={data.description ?? undefined}
        breadcrumbs={[
          { label: "Administration" },
          { label: "Roles", href: ROLES_PATH },
          { label: "Role" },
        ]}
        status={<RoleKindBadge role={data} />}
        main={
          <>
            {data.is_system && (
              <Alert tone="info" title="System role">
                MTI 360 defines this role. Its name and permissions can&apos;t
                be changed, and it can&apos;t be deleted.
              </Alert>
            )}
            <RolePermissions
              role={data}
              catalogue={
                catalogueRead.kind === "ok" ? catalogueRead.data : null
              }
              reference={
                catalogueRead.kind === "error" ? catalogueRead.reference : null
              }
            />
          </>
        }
        aside={
          <Summary
            role={data}
            canReadMembers={can(session.permissions, MEMBER_READ)}
          />
        }
      />
    </>
  );
}
