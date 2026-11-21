import { DataListTemplate } from "@/design-system/templates/DataListTemplate";
import { AddCampusButton } from "@/features/campuses/CampusDialogs";
import { CampusList } from "@/features/campuses/CampusList";
import { CAMPUSES_PATH } from "@/features/campuses/labels";
import { CAMPUS_READ } from "@/features/members/labels";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import { tenantApiRead } from "@/lib/api/server-read";
import type { TenantCampusWire } from "@/lib/api/tenant-admin";
import { settle, tenantPageAccess } from "@/lib/session/page-access";
import { SessionSync } from "@/lib/session/SessionProvider";
import { ShellAccessDenied } from "@/shells";

import type { Metadata } from "next";

// ADMIN-03 Campuses, /app/administration/campuses (02-C over the T01-08
// API). Gate: ready session → campus.read (AUTHZ-01 at this URL otherwise)
// → the campus list read on the server with the tenant cookie only. The API
// authorizes the read again and lists only the caller's campuses (D-B1).
// "Add campus" needs campus.create. Archiving is not defined (INC-40).
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Campuses · Tenant Application · MTI 360",
};

const BREADCRUMBS = [{ label: "Administration" }, { label: "Campuses" }];

export default async function CampusesPage() {
  const { session, allowed } = await tenantPageAccess(
    CAMPUSES_PATH,
    CAMPUS_READ,
  );
  if (!allowed) {
    return (
      <>
        <SessionSync session={session} />
        <ShellAccessDenied homeHref="/app" />
      </>
    );
  }
  const result = settle(
    await tenantApiRead<TenantCampusWire[]>("/campuses"),
    CAMPUSES_PATH,
  );
  return (
    <>
      <SessionSync session={session} />
      <DataListTemplate
        title="Campuses"
        description="Your institute's campuses that you have access to. Each campus has a permanent code."
        breadcrumbs={BREADCRUMBS}
        actions={<AddCampusButton />}
      >
        {result.kind === "ok" ? (
          <CampusList campuses={result.data} />
        ) : result.kind === "denied" ? (
          <ShellAccessDenied homeHref="/app" />
        ) : (
          <ReadErrorState
            title="Campuses couldn't be loaded"
            reference={result.reference}
          />
        )}
      </DataListTemplate>
    </>
  );
}
