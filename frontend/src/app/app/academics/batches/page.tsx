import { DataListTemplate } from "@/design-system/templates/DataListTemplate";
import { BatchList, NewBatchButton } from "@/features/batches/BatchList";
import { BATCH_READ, BATCHES_PATH } from "@/features/batches/labels";
import { batchListQuery, type SearchParams } from "@/features/batches/query";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import type { CourseWire } from "@/lib/api/admissions";
import type { BatchWire } from "@/lib/api/batches";
import { tenantApiRead } from "@/lib/api/server-read";
import { settle, tenantPageAccess } from "@/lib/session/page-access";
import { SessionSync } from "@/lib/session/SessionProvider";
import { ShellAccessDenied } from "@/shells";

import type { Metadata } from "next";

// ACA-05 Batches, /app/academics/batches (Phase 02-6). Gate: ready session →
// batch.read (AUTHZ-01 at this URL otherwise) → the list read on the server
// with the tenant cookie only. The API authorizes again and returns only the
// batches of the member's campuses.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Batches · Tenant Application · MTI 360",
};

const BREADCRUMBS = [{ label: "Academics" }, { label: "Batches" }];

export default async function BatchesPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const { session, allowed } = await tenantPageAccess(BATCHES_PATH, BATCH_READ);
  if (!allowed) {
    return (
      <>
        <SessionSync session={session} />
        <ShellAccessDenied homeHref="/app" />
      </>
    );
  }
  const query = batchListQuery(await searchParams);
  const [read, coursesRead] = await Promise.all([
    tenantApiRead<BatchWire[]>(`/batches?${query}`),
    tenantApiRead<CourseWire[]>("/courses?sort=code&limit=100"),
  ]);
  const result = settle(read, BATCHES_PATH);
  const courses =
    coursesRead.kind === "ok"
      ? coursesRead.data.map(({ id, code, name }) => ({ id, code, name }))
      : [];
  return (
    <>
      <SessionSync session={session} />
      <DataListTemplate
        title="Batches"
        description="Intakes of each course at your campuses, with their seats. Allocate admitted students to enrol them."
        breadcrumbs={BREADCRUMBS}
        actions={<NewBatchButton />}
      >
        {result.kind === "ok" ? (
          <BatchList
            batches={result.data}
            courses={courses}
            page={
              result.page ?? { limit: 25, offset: 0, total: result.data.length }
            }
          />
        ) : result.kind === "denied" ? (
          <ShellAccessDenied homeHref="/app" />
        ) : (
          <ReadErrorState
            title="Batches couldn't be loaded"
            reference={result.reference}
          />
        )}
      </DataListTemplate>
    </>
  );
}
