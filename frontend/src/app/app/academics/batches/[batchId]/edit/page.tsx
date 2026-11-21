import { BatchForm } from "@/features/batches/BatchForm";
import {
  BATCH_MANAGE,
  BATCHES_PATH,
  batchPath,
} from "@/features/batches/labels";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import type { BatchWire } from "@/lib/api/batches";
import { tenantApiRead } from "@/lib/api/server-read";
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

// ACA-07 Edit batch, /app/academics/batches/[batchId]/edit (Phase 02-6).
// batch.manage; course, campus and code read-only; the loaded version guards
// against lost updates (409 → "changed by someone else").
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Edit batch · Tenant Application · MTI 360",
};

type Props = { params: Promise<{ batchId: string }> };

export default async function EditBatchPage({ params }: Props) {
  const id = requireRecordId((await params).batchId);
  const path = `${batchPath(id)}/edit`;
  const { session, allowed } = await tenantPageAccess(path, BATCH_MANAGE);
  if (!allowed) {
    return (
      <>
        <SessionSync session={session} />
        <ShellAccessDenied homeHref="/app" />
      </>
    );
  }
  const result = settle(await tenantApiRead<BatchWire>(`/batches/${id}`), path);
  return (
    <>
      <SessionSync session={session} />
      {result.kind === "ok" ? (
        <PageContainer width="standard">
          <PageHeader
            title={`Edit ${result.data.code}`}
            breadcrumbs={[
              { label: "Academics" },
              { label: "Batches", href: BATCHES_PATH },
              { label: result.data.code, href: batchPath(id) },
              { label: "Edit" },
            ]}
          />
          <PageContent>
            <BatchForm batch={result.data} />
          </PageContent>
        </PageContainer>
      ) : result.kind === "denied" ? (
        <ShellAccessDenied homeHref="/app" />
      ) : (
        <PageContainer>
          <ReadErrorState
            title="This batch couldn't be loaded"
            reference={result.reference}
          />
        </PageContainer>
      )}
    </>
  );
}
