import { FeeStructureForm } from "@/features/finance/FeeStructureForm";
import {
  FEE_STRUCTURE_MANAGE,
  STRUCTURES_PATH,
} from "@/features/finance/labels";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import type { CourseWire } from "@/lib/api/admissions";
import { tenantApiRead } from "@/lib/api/server-read";
import { settle, tenantPageAccess } from "@/lib/session/page-access";
import { SessionSync } from "@/lib/session/SessionProvider";
import {
  PageContainer,
  PageContent,
  PageHeader,
  ShellAccessDenied,
} from "@/shells";

import type { Metadata } from "next";

// FIN-03 Create fee structure, /app/finance/fee-structure/new (Phase 02-5).
// fee_structure.manage is tenant-wide: campus-restricted members see AUTHZ-01
// here (and the API refuses the request regardless). The course list holds
// the institute's draft and active courses.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "New fee structure · Tenant Application · MTI 360",
};

const PATH = `${STRUCTURES_PATH}/new`;

export default async function NewFeeStructurePage() {
  const { session, allowed } = await tenantPageAccess(
    PATH,
    FEE_STRUCTURE_MANAGE,
  );
  if (!allowed) {
    return (
      <>
        <SessionSync session={session} />
        <ShellAccessDenied homeHref="/app" />
      </>
    );
  }
  const courses = settle(
    await tenantApiRead<CourseWire[]>(
      "/courses?status=ACTIVE&status=DRAFT&sort=name&limit=100",
    ),
    PATH,
  );
  return (
    <>
      <SessionSync session={session} />
      <PageContainer width="standard">
        <PageHeader
          title="New fee structure"
          description="New fee structures start as drafts. Activate one when fee invoices should use it."
          breadcrumbs={[
            { label: "Finance" },
            { label: "Fee structures", href: STRUCTURES_PATH },
            { label: "New fee structure" },
          ]}
        />
        <PageContent>
          {courses.kind === "ok" ? (
            <FeeStructureForm courses={courses.data} />
          ) : courses.kind === "denied" ? (
            <ShellAccessDenied homeHref="/app" />
          ) : (
            <ReadErrorState
              title="Courses couldn't be loaded"
              reference={courses.reference}
            />
          )}
        </PageContent>
      </PageContainer>
    </>
  );
}
