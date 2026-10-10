import {
  APPLICATION_CREATE,
  APPLICATIONS_PATH,
} from "@/features/applications/labels";
import { StartApplicationForm } from "@/features/applications/StartApplicationForm";
import { first, type SearchParams } from "@/features/courses/query";
import { COURSE_READ, LEAD_READ } from "@/features/leads/labels";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import type { CourseWire, LeadWire } from "@/lib/api/admissions";
import { tenantApiRead } from "@/lib/api/server-read";
import { can } from "@/lib/authz/requirements";
import { settle, tenantPageAccess } from "@/lib/session/page-access";
import { SessionSync } from "@/lib/session/SessionProvider";
import {
  PageContainer,
  PageContent,
  PageHeader,
  ShellAccessDenied,
} from "@/shells";

import type { Metadata } from "next";

// ADM-07 New application, /app/admissions/applications/new[?lead=<id>]
// (Phase 02-2; ADR-0021 §3). application.create; ACTIVE courses only (the API
// refuses any other). With ?lead=, the lead is read with the member's own
// rights: a lead of another campus or institute is RESOURCE-02.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "New application · Tenant Application · MTI 360",
};

const PATH = `${APPLICATIONS_PATH}/new`;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default async function NewApplicationPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const { session, allowed } = await tenantPageAccess(PATH, APPLICATION_CREATE);
  if (!allowed) {
    return (
      <>
        <SessionSync session={session} />
        <ShellAccessDenied homeHref="/app" />
      </>
    );
  }
  const leadId = first((await searchParams).lead);
  const [courses, leadRead] = await Promise.all([
    can(session.permissions, COURSE_READ)
      ? tenantApiRead<CourseWire[]>(
          "/courses?status=ACTIVE&limit=100&sort=name",
        )
      : null,
    leadId && UUID.test(leadId) && can(session.permissions, LEAD_READ)
      ? tenantApiRead<LeadWire>(`/leads/${leadId.toLowerCase()}`)
      : null,
  ]);
  const lead = leadRead ? settle(leadRead, PATH) : null;
  return (
    <>
      <SessionSync session={session} />
      <PageContainer width="standard">
        <PageHeader
          title="New application"
          description="Choose the course and campus. The application is saved as a draft and completed step by step."
          breadcrumbs={[
            { label: "Admissions" },
            { label: "Applications", href: APPLICATIONS_PATH },
            { label: "New application" },
          ]}
        />
        <PageContent>
          {lead && lead.kind !== "ok" ? (
            <ReadErrorState
              title="The lead couldn't be loaded"
              reference={lead.kind === "error" ? lead.reference : null}
            />
          ) : (
            <StartApplicationForm
              courses={courses?.kind === "ok" ? courses.data : []}
              lead={lead?.kind === "ok" ? lead.data : null}
            />
          )}
        </PageContent>
      </PageContainer>
    </>
  );
}
