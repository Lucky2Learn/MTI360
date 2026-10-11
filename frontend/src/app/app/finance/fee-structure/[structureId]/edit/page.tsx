import { Alert } from "@/design-system/components";
import { FeeStructureForm } from "@/features/finance/FeeStructureForm";
import {
  FEE_STRUCTURE_MANAGE,
  STRUCTURES_PATH,
  structurePath,
} from "@/features/finance/labels";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import type { FeeStructureWire } from "@/lib/api/finance";
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

// FIN-03 Edit fee structure, /app/finance/fee-structure/[structureId]/edit
// (Phase 02-5). Only a draft can be edited (the server refuses otherwise);
// an active or archived structure explains that a new one is needed.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Edit fee structure · Tenant Application · MTI 360",
};

type Props = { params: Promise<{ structureId: string }> };

export default async function EditFeeStructurePage({ params }: Props) {
  const id = requireRecordId((await params).structureId);
  const path = `${structurePath(id)}/edit`;
  const { session, allowed } = await tenantPageAccess(
    path,
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
  const result = settle(
    await tenantApiRead<FeeStructureWire>(`/fee-structures/${id}`),
    path,
  );
  if (result.kind !== "ok") {
    return (
      <>
        <SessionSync session={session} />
        {result.kind === "denied" ? (
          <ShellAccessDenied homeHref="/app" />
        ) : (
          <PageContainer>
            <ReadErrorState
              title="This fee structure couldn't be loaded"
              reference={result.reference}
            />
          </PageContainer>
        )}
      </>
    );
  }
  const structure = result.data;
  return (
    <>
      <SessionSync session={session} />
      <PageContainer width="standard">
        <PageHeader
          title={`Edit ${structure.name}`}
          breadcrumbs={[
            { label: "Finance" },
            { label: "Fee structures", href: STRUCTURES_PATH },
            { label: structure.name, href: structurePath(structure.id) },
            { label: "Edit" },
          ]}
        />
        <PageContent>
          {structure.status === "DRAFT" ? (
            <FeeStructureForm structure={structure} />
          ) : (
            <Alert tone="warning" title="This fee structure can't be edited">
              Only a draft can be edited. Create a new fee structure for the
              course instead.
            </Alert>
          )}
        </PageContent>
      </PageContainer>
    </>
  );
}
