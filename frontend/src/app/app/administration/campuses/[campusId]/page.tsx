import { Card, CardBody, CardHeader } from "@/design-system/components";
import { DetailTemplate } from "@/design-system/templates/DetailTemplate";
import { RenameCampusButton } from "@/features/campuses/CampusDialogs";
import { campusPath, CAMPUSES_PATH } from "@/features/campuses/labels";
import { CAMPUS_READ } from "@/features/members/labels";
import { formatDate } from "@/features/shared/format";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import { tenantApiRead } from "@/lib/api/server-read";
import type { TenantCampusWire } from "@/lib/api/tenant-admin";
import {
  requireRecordId,
  settle,
  tenantPageAccess,
} from "@/lib/session/page-access";
import { SessionSync } from "@/lib/session/SessionProvider";
import { PageContainer, ShellAccessDenied } from "@/shells";

import type { Metadata } from "next";
import type { ReactNode } from "react";

// ADMIN-04 Campus detail, /app/administration/campuses/[campusId] (02-C over
// the T01-08 API): what GET /campuses/{id} returns, and a rename with
// campus.update. A campus of another institute or outside the caller's
// campuses is RESOURCE-02 (the API answers 404, D-B1). The code never
// changes (INC-41); archiving is not defined (INC-40).
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Campus · Tenant Application · MTI 360",
};

type Props = { params: Promise<{ campusId: string }> };

function Term({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1 tablet:flex-row tablet:gap-6">
      <dt className="text-body-sm text-text-secondary tablet:w-40 tablet:shrink-0">
        {term}
      </dt>
      <dd className="min-w-0 text-body-sm break-words text-text-primary">
        {children}
      </dd>
    </div>
  );
}

export default async function CampusDetailPage({ params }: Props) {
  const id = requireRecordId((await params).campusId);
  const path = campusPath(id);
  const { session, allowed } = await tenantPageAccess(path, CAMPUS_READ);
  if (!allowed) {
    return (
      <>
        <SessionSync session={session} />
        <ShellAccessDenied homeHref="/app" />
      </>
    );
  }
  const campus = settle(
    await tenantApiRead<TenantCampusWire>(`/campuses/${id}`),
    path,
  );
  if (campus.kind !== "ok") {
    return (
      <>
        <SessionSync session={session} />
        {campus.kind === "denied" ? (
          <ShellAccessDenied homeHref="/app" />
        ) : (
          <PageContainer>
            <ReadErrorState
              title="This campus couldn't be loaded"
              reference={campus.reference}
            />
          </PageContainer>
        )}
      </>
    );
  }
  const data = campus.data;

  return (
    <>
      <SessionSync session={session} />
      <DetailTemplate
        title={data.name}
        description={`Campus code ${data.code}`}
        breadcrumbs={[
          { label: "Administration" },
          { label: "Campuses", href: CAMPUSES_PATH },
          { label: "Campus" },
        ]}
        actions={<RenameCampusButton campus={data} />}
        main={
          <Card as="section" aria-labelledby="campus-details">
            <CardHeader title="Details" titleAs="h2" titleId="campus-details" />
            <CardBody>
              <dl className="flex flex-col gap-4">
                <Term term="Name">{data.name}</Term>
                <Term term="Code">
                  <span className="flex flex-col gap-1">
                    <span className="break-all">{data.code}</span>
                    <span className="text-caption text-text-secondary">
                      Set when the campus was added. It can&apos;t be changed.
                    </span>
                  </span>
                </Term>
                <Term term="Added">{formatDate(data.created_at)}</Term>
                <Term term="Last changed">{formatDate(data.updated_at)}</Term>
              </dl>
            </CardBody>
          </Card>
        }
      />
    </>
  );
}
