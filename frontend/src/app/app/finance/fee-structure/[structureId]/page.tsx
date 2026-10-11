import { Badge, Card, CardBody, CardHeader } from "@/design-system/components";
import { DetailTemplate } from "@/design-system/templates/DetailTemplate";
import { FeeStructureActions } from "@/features/finance/FeeStructureActions";
import {
  FEE_STRUCTURE_READ,
  STRUCTURE_STATUS_LABEL,
  STRUCTURE_STATUS_TONE,
  STRUCTURES_PATH,
  structurePath,
} from "@/features/finance/labels";
import { formatPaise } from "@/features/finance/money";
import { Term } from "@/features/finance/Term";
import { formatDate } from "@/features/shared/format";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import type { FeeStructureWire } from "@/lib/api/finance";
import { tenantApiRead } from "@/lib/api/server-read";
import {
  requireRecordId,
  settle,
  tenantPageAccess,
} from "@/lib/session/page-access";
import { SessionSync } from "@/lib/session/SessionProvider";
import { PageContainer, ShellAccessDenied } from "@/shells";

import type { Metadata } from "next";

// FIN-03 Fee structure detail, /app/finance/fee-structure/[structureId]
// (Phase 02-5). Another institute's structure, or a malformed ID, is
// RESOURCE-02 (the API answers 404 for both). Actions need
// fee_structure.manage (PermissionGate; the API decides).
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Fee structure · Tenant Application · MTI 360",
};

type Props = { params: Promise<{ structureId: string }> };

export default async function FeeStructurePage({ params }: Props) {
  const id = requireRecordId((await params).structureId);
  const path = structurePath(id);
  const { session, allowed } = await tenantPageAccess(path, FEE_STRUCTURE_READ);
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
      <DetailTemplate
        title={structure.name}
        description={`${structure.course.code} · ${structure.course.name}`}
        breadcrumbs={[
          { label: "Finance" },
          { label: "Fee structures", href: STRUCTURES_PATH },
          { label: structure.name },
        ]}
        status={
          <Badge tone={STRUCTURE_STATUS_TONE[structure.status]}>
            {STRUCTURE_STATUS_LABEL[structure.status]}
          </Badge>
        }
        actions={<FeeStructureActions structure={structure} />}
        asideLabel="Fee structure summary"
        main={
          <Card as="section">
            <CardHeader title="Fee heads" titleAs="h2" />
            <CardBody>
              <table className="w-full text-body-sm">
                <caption className="sr-only">Fee heads and amounts</caption>
                <thead>
                  <tr className="border-b border-border-subtle text-left text-text-secondary">
                    <th scope="col" className="py-2 font-medium">
                      Fee head
                    </th>
                    <th scope="col" className="py-2 text-right font-medium">
                      Amount
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {structure.items.map((item) => (
                    <tr
                      key={item.fee_head}
                      className="border-b border-border-subtle"
                    >
                      <th
                        scope="row"
                        className="py-2 text-left font-normal text-text-primary"
                      >
                        {item.fee_head}
                      </th>
                      <td className="py-2 text-right tabular-nums text-text-primary">
                        {formatPaise(item.amount_minor)}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <th
                      scope="row"
                      className="pt-3 text-left font-medium text-text-primary"
                    >
                      Total
                    </th>
                    <td className="pt-3 text-right font-medium tabular-nums text-text-primary">
                      {formatPaise(structure.total_minor)}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </CardBody>
          </Card>
        }
        aside={
          <Card as="section">
            <CardHeader title="Summary" titleAs="h2" />
            <CardBody>
              <dl className="flex flex-col gap-4">
                <Term term="Course">{`${structure.course.code} · ${structure.course.name}`}</Term>
                <Term term="Status">
                  {STRUCTURE_STATUS_LABEL[structure.status]}
                </Term>
                <Term term="Activated">
                  {structure.activated_at
                    ? formatDate(structure.activated_at)
                    : "Not yet"}
                </Term>
                {structure.archived_at && (
                  <Term term="Archived">
                    {formatDate(structure.archived_at)}
                  </Term>
                )}
                <Term term="Last updated">
                  {formatDate(structure.updated_at)}
                </Term>
              </dl>
            </CardBody>
          </Card>
        }
      />
    </>
  );
}
