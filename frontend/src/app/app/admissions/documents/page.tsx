import { DataListTemplate } from "@/design-system/templates/DataListTemplate";
import { DOCUMENT_READ, DOCUMENTS_PATH } from "@/features/applications/labels";
import { documentQueueQuery } from "@/features/applications/query";
import type { SearchParams } from "@/features/courses/query";
import { DocumentQueue } from "@/features/documents/DocumentQueue";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import type { QueueItemWire } from "@/lib/api/admissions";
import { tenantApiRead } from "@/lib/api/server-read";
import { settle, tenantPageAccess } from "@/lib/session/page-access";
import { SessionSync } from "@/lib/session/SessionProvider";
import { ShellAccessDenied } from "@/shells";

import type { Metadata } from "next";

// ADM-09 Document verification queue, /app/admissions/documents (Phase 02-2;
// ADR-0021 §5, §14). Gate: ready session → document.read → the queue read on
// the server with the tenant cookie only; the API applies the campus rule.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Documents · Tenant Application · MTI 360",
};

export default async function DocumentsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const { session, allowed } = await tenantPageAccess(
    DOCUMENTS_PATH,
    DOCUMENT_READ,
  );
  if (!allowed) {
    return (
      <>
        <SessionSync session={session} />
        <ShellAccessDenied homeHref="/app" />
      </>
    );
  }
  const query = documentQueueQuery(await searchParams);
  const result = settle(
    await tenantApiRead<QueueItemWire[]>(`/documents?${query}`),
    DOCUMENTS_PATH,
  );
  return (
    <>
      <SessionSync session={session} />
      <DataListTemplate
        title="Document verification"
        description="Application documents awaiting verification, oldest first."
        breadcrumbs={[{ label: "Admissions" }, { label: "Documents" }]}
      >
        {result.kind === "ok" ? (
          <DocumentQueue
            items={result.data}
            page={
              result.page ?? { limit: 25, offset: 0, total: result.data.length }
            }
          />
        ) : result.kind === "denied" ? (
          <ShellAccessDenied homeHref="/app" />
        ) : (
          <ReadErrorState
            title="Documents couldn't be loaded"
            reference={result.reference}
          />
        )}
      </DataListTemplate>
    </>
  );
}
