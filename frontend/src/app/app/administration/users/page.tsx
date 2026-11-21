import { DataListTemplate } from "@/design-system/templates/DataListTemplate";
import type { SearchParams } from "@/features/courses/query";
import { InviteMemberButton } from "@/features/members/InviteMemberDialog";
import { MEMBER_READ, MEMBERS_PATH } from "@/features/members/labels";
import { MemberList } from "@/features/members/MemberList";
import { memberListQuery } from "@/features/members/query";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import { tenantApiRead } from "@/lib/api/server-read";
import type { MemberWire } from "@/lib/api/tenant-admin";
import { settle, tenantPageAccess } from "@/lib/session/page-access";
import { SessionSync } from "@/lib/session/SessionProvider";
import { ShellAccessDenied } from "@/shells";

import type { Metadata } from "next";

// ADMIN-05 Users, /app/administration/users (02-C over the T01-08 API).
// Gate: ready session → member.read (AUTHZ-01 at this URL otherwise) → the
// member list read on the server with the tenant cookie only. The API
// authorizes the read again and lists the session's institute only.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Users · Tenant Application · MTI 360",
};

const BREADCRUMBS = [{ label: "Administration" }, { label: "Users" }];

export default async function UsersPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const { session, allowed } = await tenantPageAccess(
    MEMBERS_PATH,
    MEMBER_READ,
  );
  if (!allowed) {
    return (
      <>
        <SessionSync session={session} />
        <ShellAccessDenied homeHref="/app" />
      </>
    );
  }
  const query = memberListQuery(await searchParams);
  const result = settle(
    await tenantApiRead<MemberWire[]>(`/members?${query}`),
    MEMBERS_PATH,
  );
  return (
    <>
      <SessionSync session={session} />
      <DataListTemplate
        title="Users"
        description="Your institute's members: the staff who can sign in, their roles and the campuses they work with."
        breadcrumbs={BREADCRUMBS}
        actions={<InviteMemberButton />}
      >
        {result.kind === "ok" ? (
          <MemberList
            members={result.data}
            page={
              result.page ?? { limit: 25, offset: 0, total: result.data.length }
            }
          />
        ) : result.kind === "denied" ? (
          <ShellAccessDenied homeHref="/app" />
        ) : (
          <ReadErrorState
            title="Members couldn't be loaded"
            reference={result.reference}
          />
        )}
      </DataListTemplate>
    </>
  );
}
