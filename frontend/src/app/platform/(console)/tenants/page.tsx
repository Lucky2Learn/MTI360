import { DataListTemplate } from "@/design-system/templates/DataListTemplate";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import { TENANT_READ, TENANTS_PATH } from "@/features/tenants/labels";
import { PlatformDenied } from "@/features/tenants/PlatformDenied";
import { tenantListQuery, type SearchParams } from "@/features/tenants/query";
import { NewTenantButton, TenantList } from "@/features/tenants/TenantList";
import type { TenantWire } from "@/lib/api/platform-tenants";
import { platformApiRead } from "@/lib/api/server-read";
import {
  platformPageAccess,
  settlePlatform,
} from "@/lib/session/platform-page-access";
import { PlatformSessionSync } from "@/lib/session/PlatformSessionProvider";

import type { Metadata } from "next";

// PLAT-04 Tenant list, /platform/tenants (replaces the navigation
// placeholder). Gate: full platform session → tenant.read (access denied at
// this URL otherwise) → the list read on the server with the platform cookie
// only. The platform API authorizes the read again; a tenant session can
// never reach it (realm guard).
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Tenants · Platform Administration · MTI 360",
};

export default async function TenantsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const { session, allowed } = await platformPageAccess(
    TENANTS_PATH,
    TENANT_READ,
  );
  if (!allowed) {
    return (
      <>
        <PlatformSessionSync session={session} />
        <PlatformDenied />
      </>
    );
  }
  const query = tenantListQuery(await searchParams);
  const result = settlePlatform(
    await platformApiRead<TenantWire[]>(`/tenants?${query}`),
    TENANTS_PATH,
  );
  return (
    <>
      <PlatformSessionSync session={session} />
      <DataListTemplate
        title="Tenants"
        description="Every maritime training institute on MTI 360, with its lifecycle status."
        breadcrumbs={[{ label: "Tenants" }]}
        actions={<NewTenantButton />}
      >
        {result.kind === "ok" ? (
          <TenantList
            tenants={result.data}
            page={
              result.page ?? { limit: 25, offset: 0, total: result.data.length }
            }
          />
        ) : result.kind === "denied" ? (
          <PlatformDenied />
        ) : (
          <ReadErrorState
            title="Tenants couldn't be loaded"
            reference={result.reference}
          />
        )}
      </DataListTemplate>
    </>
  );
}
