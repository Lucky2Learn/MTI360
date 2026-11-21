import { Badge, Card, CardBody, CardHeader } from "@/design-system/components";
import { DetailTemplate } from "@/design-system/templates/DetailTemplate";
import { formatDate, formatDateTime } from "@/features/shared/format";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import {
  OWNER_STATUS_LABEL,
  STATUS_LABEL,
  STATUS_TONE,
  TENANT_READ,
  TENANTS_PATH,
  tenantPath,
} from "@/features/tenants/labels";
import { PlatformDenied } from "@/features/tenants/PlatformDenied";
import {
  ResendInvitationAction,
  TenantLifecycleActions,
} from "@/features/tenants/TenantActions";
import type { TenantDetailWire } from "@/lib/api/platform-tenants";
import { platformApiRead } from "@/lib/api/server-read";
import { requireRecordId } from "@/lib/session/page-access";
import {
  platformPageAccess,
  settlePlatform,
} from "@/lib/session/platform-page-access";
import { PlatformSessionSync } from "@/lib/session/PlatformSessionProvider";
import { PageContainer } from "@/shells";

import type { Metadata } from "next";
import type { ReactNode } from "react";

// PLAT-05 Tenant detail (partial), /platform/tenants/[tenantId]. The tenant
// in the URL is a target only: the platform API reads it under the platform
// session and never makes it the request's tenant. A malformed or unknown ID
// is not found. The owner block is the primary administrator only; no other
// member, token or tenant data is shown. Actions: suspend / reactivate and
// resending the owner invitation (features/tenants/TenantActions).
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Tenant · Platform Administration · MTI 360",
};

type Props = { params: Promise<{ tenantId: string }> };

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

export default async function TenantDetailPage({ params }: Props) {
  const id = requireRecordId((await params).tenantId);
  const path = tenantPath(id);
  const { session, allowed } = await platformPageAccess(path, TENANT_READ);
  if (!allowed) {
    return (
      <>
        <PlatformSessionSync session={session} />
        <PlatformDenied />
      </>
    );
  }
  const result = settlePlatform(
    await platformApiRead<TenantDetailWire>(`/tenants/${id}`),
    path,
  );
  if (result.kind !== "ok") {
    return (
      <>
        <PlatformSessionSync session={session} />
        {result.kind === "denied" ? (
          <PlatformDenied />
        ) : (
          <PageContainer>
            <ReadErrorState
              title="This tenant couldn't be loaded"
              reference={result.reference}
            />
          </PageContainer>
        )}
      </>
    );
  }
  const tenant = result.data;
  const owner = tenant.owner;
  return (
    <>
      <PlatformSessionSync session={session} />
      <DetailTemplate
        title={tenant.name}
        description={`Created ${formatDate(tenant.created_at)}`}
        breadcrumbs={[
          { label: "Tenants", href: TENANTS_PATH },
          { label: tenant.name },
        ]}
        status={
          <Badge tone={STATUS_TONE[tenant.status]}>
            {STATUS_LABEL[tenant.status]}
          </Badge>
        }
        actions={<TenantLifecycleActions tenant={tenant} />}
        asideLabel="Tenant summary"
        main={
          <Card as="section">
            <CardHeader
              title="Administrator"
              titleAs="h2"
              actions={<ResendInvitationAction tenant={tenant} />}
            />
            <CardBody>
              {owner ? (
                <dl className="flex flex-col gap-4">
                  <Term term="Name">{owner.display_name}</Term>
                  <Term term="Email">{owner.email}</Term>
                  <Term term="Status">{OWNER_STATUS_LABEL[owner.status]}</Term>
                </dl>
              ) : (
                <p className="text-body-sm text-text-secondary">
                  No administrator is recorded for this institute.
                </p>
              )}
            </CardBody>
          </Card>
        }
        aside={
          <Card as="section">
            <CardHeader title="Summary" titleAs="h2" />
            <CardBody>
              <dl className="flex flex-col gap-4">
                <Term term="Status">{STATUS_LABEL[tenant.status]}</Term>
                <Term term="Created">{formatDate(tenant.created_at)}</Term>
                <Term term="Last updated">
                  {formatDateTime(tenant.updated_at)}
                </Term>
              </dl>
            </CardBody>
          </Card>
        }
      />
    </>
  );
}
