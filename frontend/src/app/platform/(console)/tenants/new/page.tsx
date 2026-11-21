import {
  NEW_TENANT_PATH,
  TENANT_CREATE,
  TENANTS_PATH,
} from "@/features/tenants/labels";
import { PlatformDenied } from "@/features/tenants/PlatformDenied";
import { TenantForm } from "@/features/tenants/TenantForm";
import { platformPageAccess } from "@/lib/session/platform-page-access";
import { PlatformSessionSync } from "@/lib/session/PlatformSessionProvider";
import { PageContainer, PageContent, PageHeader } from "@/shells";

import type { Metadata } from "next";

// PLAT-06 Create tenant, /platform/tenants/new. Gate: full platform session →
// tenant.create (access denied at this URL otherwise). The platform API
// authorizes the provisioning request again.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "New tenant · Platform Administration · MTI 360",
};

export default async function NewTenantPage() {
  const { session, allowed } = await platformPageAccess(
    NEW_TENANT_PATH,
    TENANT_CREATE,
  );
  return (
    <>
      <PlatformSessionSync session={session} />
      {allowed ? (
        <PageContainer width="standard">
          <PageHeader
            title="New tenant"
            description="Provision an institute, its primary campus and its administrator's invitation."
            breadcrumbs={[
              { label: "Tenants", href: TENANTS_PATH },
              { label: "New tenant" },
            ]}
          />
          <PageContent>
            <TenantForm />
          </PageContent>
        </PageContainer>
      ) : (
        <PlatformDenied />
      )}
    </>
  );
}
