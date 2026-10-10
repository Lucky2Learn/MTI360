import { DataListTemplate } from "@/design-system/templates/DataListTemplate";
import {
  ApplicationList,
  NewApplicationButton,
} from "@/features/applications/ApplicationList";
import {
  APPLICATION_READ,
  APPLICATIONS_PATH,
} from "@/features/applications/labels";
import { applicationListQuery } from "@/features/applications/query";
import type { SearchParams } from "@/features/courses/query";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import type { ApplicationListItemWire } from "@/lib/api/admissions";
import { tenantApiRead } from "@/lib/api/server-read";
import { settle, tenantPageAccess } from "@/lib/session/page-access";
import { SessionSync } from "@/lib/session/SessionProvider";
import { ShellAccessDenied } from "@/shells";

import type { Metadata } from "next";

// ADM-05 Applications, /app/admissions/applications (Phase 02-2; ADR-0021
// §14). Gate: ready session → application.read (AUTHZ-01 at this URL
// otherwise) → the list read on the server with the tenant cookie only. The
// API applies the campus rule: members see their campuses' applications.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Applications · Tenant Application · MTI 360",
};

const BREADCRUMBS = [{ label: "Admissions" }, { label: "Applications" }];

export default async function ApplicationsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const { session, allowed } = await tenantPageAccess(
    APPLICATIONS_PATH,
    APPLICATION_READ,
  );
  if (!allowed) {
    return (
      <>
        <SessionSync session={session} />
        <ShellAccessDenied homeHref="/app" />
      </>
    );
  }
  const query = applicationListQuery(await searchParams);
  const result = settle(
    await tenantApiRead<ApplicationListItemWire[]>(`/applications?${query}`),
    APPLICATIONS_PATH,
  );
  return (
    <>
      <SessionSync session={session} />
      <DataListTemplate
        title="Applications"
        description="Staff-assisted applications, from draft to admission."
        breadcrumbs={BREADCRUMBS}
        actions={<NewApplicationButton />}
      >
        {result.kind === "ok" ? (
          <ApplicationList
            applications={result.data}
            page={
              result.page ?? { limit: 25, offset: 0, total: result.data.length }
            }
          />
        ) : result.kind === "denied" ? (
          <ShellAccessDenied homeHref="/app" />
        ) : (
          <ReadErrorState
            title="Applications couldn't be loaded"
            reference={result.reference}
          />
        )}
      </DataListTemplate>
    </>
  );
}
