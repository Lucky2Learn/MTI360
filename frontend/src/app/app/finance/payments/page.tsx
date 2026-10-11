import { DataListTemplate } from "@/design-system/templates/DataListTemplate";
import { INVOICE_READ, PAYMENTS_PATH } from "@/features/finance/labels";
import { PaymentList } from "@/features/finance/PaymentList";
import { paymentListQuery, type SearchParams } from "@/features/finance/query";
import { sessionCampuses } from "@/features/finance/server";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import type { PaymentWire } from "@/lib/api/finance";
import { tenantApiRead } from "@/lib/api/server-read";
import { settle, tenantPageAccess } from "@/lib/session/page-access";
import { SessionSync } from "@/lib/session/SessionProvider";
import { ShellAccessDenied } from "@/shells";

import type { Metadata } from "next";

// FIN-06 Payments, /app/finance/payments (Phase 02-5; readiness plan §4).
// Gate: ready session → invoice.read (payments and receipts are read with
// it) → the list read on the server; the API scopes it to the tenant and
// the caller's campuses.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Payments · Tenant Application · MTI 360",
};

const BREADCRUMBS = [{ label: "Finance" }, { label: "Payments" }];

export default async function PaymentsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const { session, allowed } = await tenantPageAccess(
    PAYMENTS_PATH,
    INVOICE_READ,
  );
  if (!allowed) {
    return (
      <>
        <SessionSync session={session} />
        <ShellAccessDenied homeHref="/app" />
      </>
    );
  }
  const query = paymentListQuery(await searchParams);
  const result = settle(
    await tenantApiRead<PaymentWire[]>(`/payments?${query}`),
    PAYMENTS_PATH,
  );
  return (
    <>
      <SessionSync session={session} />
      <DataListTemplate
        title="Payments"
        description="Offline fee payments at your campuses: cash, UPI, bank transfers, cheques and demand drafts."
        breadcrumbs={BREADCRUMBS}
      >
        {result.kind === "ok" ? (
          <PaymentList
            payments={result.data}
            page={
              result.page ?? {
                limit: 25,
                offset: 0,
                total: result.data.length,
              }
            }
            campuses={sessionCampuses(session)}
          />
        ) : result.kind === "denied" ? (
          <ShellAccessDenied homeHref="/app" />
        ) : (
          <ReadErrorState
            title="Payments couldn't be loaded"
            reference={result.reference}
          />
        )}
      </DataListTemplate>
    </>
  );
}
