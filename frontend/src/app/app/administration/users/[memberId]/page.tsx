import {
  Alert,
  Badge,
  Card,
  CardBody,
  CardHeader,
} from "@/design-system/components";
import { DetailTemplate } from "@/design-system/templates/DetailTemplate";
import {
  CAMPUS_READ,
  isOwnMembership,
  MEMBER_READ,
  MEMBERS_PATH,
  memberPath,
  ROLE_READ,
  STATUS_DESCRIPTION,
  STATUS_LABEL,
  STATUS_TONE,
} from "@/features/members/labels";
import { MemberActions } from "@/features/members/MemberActions";
import { MemberCampuses } from "@/features/members/MemberCampuses";
import { MemberRoles } from "@/features/members/MemberRoles";
import { formatDate } from "@/features/shared/format";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import { tenantApiRead } from "@/lib/api/server-read";
import type {
  MemberWire,
  TenantCampusWire,
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

// ADMIN-06 User detail, /app/administration/users/[memberId] (02-C over the
// T01-08 API). The member, the institute's roles (role.read) and the
// caller's campuses (campus.read) are read in parallel on the server. A
// member of another institute is RESOURCE-02 (the API answers 404). The
// person's name is never put in the page title or the URL.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "User · Tenant Application · MTI 360",
};

type Props = { params: Promise<{ memberId: string }> };

function Term({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1 tablet:flex-row tablet:gap-6">
      <dt className="text-body-sm text-text-secondary tablet:w-40 tablet:shrink-0">
        {term}
      </dt>
      <dd className="min-w-0 text-body-sm break-words text-text-primary">
        {children}
      </dd>
    </div>
  );
}

function Membership({ member }: { member: MemberWire }) {
  return (
    <Card as="section">
      <CardHeader title="Membership" titleAs="h2" />
      <CardBody>
        <dl className="flex flex-col gap-4">
          <Term term="Email">
            <span className="break-all">{member.user.email}</span>
          </Term>
          <Term term="Status">
            <span className="flex flex-col gap-1">
              <Badge tone={STATUS_TONE[member.status]}>
                {STATUS_LABEL[member.status]}
              </Badge>
              <span className="text-caption text-text-secondary">
                {STATUS_DESCRIPTION[member.status]}
              </span>
            </span>
          </Term>
          <Term term="Invited">{formatDate(member.invited_at)}</Term>
          <Term term="Joined">
            {member.joined_at ? formatDate(member.joined_at) : "Not yet"}
          </Term>
        </dl>
      </CardBody>
    </Card>
  );
}

export default async function UserDetailPage({ params }: Props) {
  const id = requireRecordId((await params).memberId);
  const path = memberPath(id);
  const { session, allowed } = await tenantPageAccess(path, MEMBER_READ);
  if (!allowed) {
    return (
      <>
        <SessionSync session={session} />
        <ShellAccessDenied homeHref="/app" />
      </>
    );
  }
  const [memberRead, rolesRead, campusesRead] = await Promise.all([
    tenantApiRead<MemberWire>(`/members/${id}`),
    can(session.permissions, ROLE_READ)
      ? tenantApiRead<TenantRoleWire[]>("/roles")
      : null,
    can(session.permissions, CAMPUS_READ)
      ? tenantApiRead<TenantCampusWire[]>("/campuses")
      : null,
  ]);
  const member = settle(memberRead, path);
  if (member.kind !== "ok") {
    return (
      <>
        <SessionSync session={session} />
        {member.kind === "denied" ? (
          <ShellAccessDenied homeHref="/app" />
        ) : (
          <PageContainer>
            <ReadErrorState
              title="This member couldn't be loaded"
              reference={member.reference}
            />
          </PageContainer>
        )}
      </>
    );
  }
  const data = member.data;
  const own = isOwnMembership(data, session.user.email);

  return (
    <>
      <SessionSync session={session} />
      <DetailTemplate
        title={data.user.display_name}
        description={own ? "Your membership" : data.user.email}
        breadcrumbs={[
          { label: "Administration" },
          { label: "Users", href: MEMBERS_PATH },
          { label: "User" },
        ]}
        status={
          <Badge tone={STATUS_TONE[data.status]}>
            {STATUS_LABEL[data.status]}
          </Badge>
        }
        actions={<MemberActions member={data} />}
        asideLabel="Campus access"
        main={
          <>
            {own && (
              <Alert tone="info" title="This is your own membership">
                Another administrator changes your status, campus access and
                role removals, so your institute is never locked out.
              </Alert>
            )}
            <Membership member={data} />
            <MemberRoles
              member={data}
              roles={rolesRead?.kind === "ok" ? rolesRead.data : null}
            />
          </>
        }
        aside={
          <MemberCampuses
            member={data}
            campuses={campusesRead?.kind === "ok" ? campusesRead.data : null}
          />
        }
      />
    </>
  );
}
