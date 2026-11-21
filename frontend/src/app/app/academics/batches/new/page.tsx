import { BatchForm } from "@/features/batches/BatchForm";
import { BATCH_MANAGE, BATCHES_PATH } from "@/features/batches/labels";
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

// ACA-07 Create batch, /app/academics/batches/new (Phase 02-6). batch.manage;
// the course list is the active courses (the API refuses any other).
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "New batch · Tenant Application · MTI 360",
};

const PATH = `${BATCHES_PATH}/new`;

export default async function NewBatchPage() {
  const { session, allowed } = await tenantPageAccess(PATH, BATCH_MANAGE);
  if (!allowed) {
    return (
      <>
        <SessionSync session={session} />
        <ShellAccessDenied homeHref="/app" />
      </>
    );
  }
  const result = settle(
    await tenantApiRead<CourseWire[]>(
      "/courses?status=ACTIVE&sort=code&limit=100",
    ),
    PATH,
  );
  return (
    <>
      <SessionSync session={session} />
      <PageContainer width="standard">
        <PageHeader
          title="New batch"
          description="New batches are open for allocation. Close a batch to stop allocations."
          breadcrumbs={[
            { label: "Academics" },
            { label: "Batches", href: BATCHES_PATH },
            { label: "New batch" },
          ]}
        />
        <PageContent>
          {result.kind === "ok" ? (
            <BatchForm
              courses={result.data.map(({ id, code, name }) => ({
                id,
                code,
                name,
              }))}
            />
          ) : result.kind === "denied" ? (
            <ShellAccessDenied homeHref="/app" />
          ) : (
            <ReadErrorState
              title="Courses couldn't be loaded"
              reference={result.reference}
            />
          )}
        </PageContent>
      </PageContainer>
    </>
  );
}
