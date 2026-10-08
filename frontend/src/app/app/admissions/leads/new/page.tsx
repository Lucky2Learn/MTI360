import { COURSE_READ, LEAD_CREATE, LEADS_PATH } from "@/features/leads/labels";
import { LeadForm } from "@/features/leads/LeadForm";
import type { CourseWire } from "@/lib/api/admissions";
import { tenantApiRead } from "@/lib/api/server-read";
import { can } from "@/lib/authz/requirements";
import { tenantPageAccess } from "@/lib/session/page-access";
import { SessionSync } from "@/lib/session/SessionProvider";
import {
  PageContainer,
  PageContent,
  PageHeader,
  ShellAccessDenied,
} from "@/shells";

import type { Metadata } from "next";

// New lead, /app/admissions/leads/new (Phase 02-1; GROW-08 primary action).
// lead.create; the course list holds ACTIVE courses only (the API refuses any
// other). Campus options are the member's own campuses plus institute-wide.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "New lead · Tenant Application · MTI 360",
};

const PATH = `${LEADS_PATH}/new`;

export default async function NewLeadPage() {
  const { session, allowed } = await tenantPageAccess(PATH, LEAD_CREATE);
  if (!allowed) {
    return (
      <>
        <SessionSync session={session} />
        <ShellAccessDenied homeHref="/app" />
      </>
    );
  }
  const courses = can(session.permissions, COURSE_READ)
    ? await tenantApiRead<CourseWire[]>(
        "/courses?status=ACTIVE&limit=100&sort=name",
      )
    : null;
  return (
    <>
      <SessionSync session={session} />
      <PageContainer width="standard">
        <PageHeader
          title="New lead"
          description="Record an enquiry. You'll be warned if it may already exist."
          breadcrumbs={[
            { label: "Admissions" },
            { label: "Leads", href: LEADS_PATH },
            { label: "New lead" },
          ]}
        />
        <PageContent>
          <LeadForm courses={courses?.kind === "ok" ? courses.data : []} />
        </PageContent>
      </PageContainer>
    </>
  );
}
