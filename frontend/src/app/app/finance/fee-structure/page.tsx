import { DataListTemplate } from "@/design-system/templates/DataListTemplate";
import {
  FeeStructureList,
  NewStructureButton,
} from "@/features/finance/FeeStructureList";
import { FEE_STRUCTURE_READ, STRUCTURES_PATH } from "@/features/finance/labels";
import {
  structureListQuery,
  type SearchParams,
} from "@/features/finance/query";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import type { FeeStructureWire } from "@/lib/api/finance";
import { tenantApiRead } from "@/lib/api/server-read";
import { settle, tenantPageAccess } from "@/lib/session/page-access";
import { SessionSync } from "@/lib/session/SessionProvider";
import { ShellAccessDenied } from "@/shells";

import type { Metadata } from "next";

// FIN-02 Fee structures, /app/finance/fee-structure (Phase 02-5). Gate: ready
// session → fee_structure.read (AUTHZ-01 at this URL otherwise) → the list
// read on the server with the tenant cookie only. The API authorizes again;
// structures are institute-wide, so campus-restricted staff see all of them.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Fee structures · Tenant Application · MTI 360",
};

const BREADCRUMBS = [{ label: "Finance" }, { label: "Fee structures" }];

export default async function FeeStructuresPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const { session, allowed } = await tenantPageAccess(
    STRUCTURES_PATH,
    FEE_STRUCTURE_READ,
  );
  if (!allowed) {
    return (
      <>
        <SessionSync session={session} />
        <ShellAccessDenied homeHref="/app" />
      </>
    );
  }
  const query = structureListQuery(await searchParams);
  const result = settle(
    await tenantApiRead<FeeStructureWire[]>(`/fee-structures?${query}`),
    STRUCTURES_PATH,
  );
  return (
    <>
      <SessionSync session={session} />
      <DataListTemplate
        title="Fee structures"
        description="The fee heads of each course. Fee invoices for admitted students are issued from the course's active fee structure."
        breadcrumbs={BREADCRUMBS}
        actions={<NewStructureButton />}
      >
        {result.kind === "ok" ? (
          <FeeStructureList
            structures={result.data}
            page={
              result.page ?? { limit: 25, offset: 0, total: result.data.length }
            }
          />
        ) : result.kind === "denied" ? (
          <ShellAccessDenied homeHref="/app" />
        ) : (
          <ReadErrorState
            title="Fee structures couldn't be loaded"
            reference={result.reference}
          />
        )}
      </DataListTemplate>
    </>
  );
}
