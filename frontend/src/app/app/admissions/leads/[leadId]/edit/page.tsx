import {
  COURSE_READ,
  LEAD_UPDATE,
  LEADS_PATH,
  leadPath,
} from "@/features/leads/labels";
import { LeadForm } from "@/features/leads/LeadForm";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import type { CourseWire, LeadWire } from "@/lib/api/admissions";
import { tenantApiRead } from "@/lib/api/server-read";
import { can } from "@/lib/authz/requirements";
import {
  requireRecordId,
  settle,
  tenantPageAccess,
} from "@/lib/session/page-access";
import { SessionSync } from "@/lib/session/SessionProvider";
import {
  PageContainer,
  PageContent,
  PageHeader,
  ShellAccessDenied,
} from "@/shells";

import type { Metadata } from "next";

// Edit lead, /app/admissions/leads/[leadId]/edit (Phase 02-1). lead.update;
// contact, source, course and the optional details. Campus and owner change
// through "Assign…" on the detail page. The loaded version guards against
// lost updates.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Edit lead · Tenant Application · MTI 360",
};

type Props = { params: Promise<{ leadId: string }> };

export default async function EditLeadPage({ params }: Props) {
  const id = requireRecordId((await params).leadId);
  const path = `${leadPath(id)}/edit`;
  const { session, allowed } = await tenantPageAccess(path, LEAD_UPDATE);
  if (!allowed) {
    return (
      <>
        <SessionSync session={session} />
        <ShellAccessDenied homeHref="/app" />
      </>
    );
  }
  const [leadRead, courses] = await Promise.all([
    tenantApiRead<LeadWire>(`/leads/${id}`),
    can(session.permissions, COURSE_READ)
      ? tenantApiRead<CourseWire[]>(
          "/courses?status=ACTIVE&limit=100&sort=name",
        )
      : null,
  ]);
  const lead = settle(leadRead, path);
  return (
    <>
      <SessionSync session={session} />
      {lead.kind === "ok" ? (
        <PageContainer width="standard">
          <PageHeader
            title="Edit lead"
            description={lead.data.full_name}
            breadcrumbs={[
              { label: "Admissions" },
              { label: "Leads", href: LEADS_PATH },
              { label: "Lead", href: leadPath(id) },
              { label: "Edit" },
            ]}
          />
          <PageContent>
            <LeadForm
              lead={lead.data}
              courses={courses?.kind === "ok" ? courses.data : []}
            />
          </PageContent>
        </PageContainer>
      ) : lead.kind === "denied" ? (
        <ShellAccessDenied homeHref="/app" />
      ) : (
        <PageContainer>
          <ReadErrorState
            title="This lead couldn't be loaded"
            reference={lead.reference}
          />
        </PageContainer>
      )}
    </>
  );
}
