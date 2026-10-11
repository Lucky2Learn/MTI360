import { DataListTemplate } from "@/design-system/templates/DataListTemplate";
import { first } from "@/features/courses/query";
import { InvoiceList } from "@/features/finance/InvoiceList";
import { INVOICE_READ, OUTSTANDING_PATH } from "@/features/finance/labels";
import {
  invoiceListQuery,
  isRecordId,
  type SearchParams,
} from "@/features/finance/query";
import {
  courseFilterOptions,
  sessionCampuses,
} from "@/features/finance/server";
import { SummaryStrip } from "@/features/finance/SummaryStrip";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import type { FinanceSummaryWire, InvoiceWire } from "@/lib/api/finance";
import { tenantApiRead } from "@/lib/api/server-read";
import { settle, tenantPageAccess } from "@/lib/session/page-access";
import { SessionSync } from "@/lib/session/SessionProvider";
import { ShellAccessDenied } from "@/shells";

import type { Metadata } from "next";

// FIN-08 Outstanding, /app/finance/outstanding (Phase 02-5; readiness plan
// §2, §4, J6): fee invoices with a balance still to collect, oldest due
// first, under the server's summary strip. Both reads are scoped by the API
// to the tenant and the caller's campuses; the campus filter narrows both.
// FIN-01 (the finance dashboard) is deferred: no invented numbers.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Outstanding fees · Tenant Application · MTI 360",
};

const BREADCRUMBS = [{ label: "Finance" }, { label: "Outstanding" }];

export default async function OutstandingPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const { session, allowed } = await tenantPageAccess(
    OUTSTANDING_PATH,
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
  const params = await searchParams;
  const campus = first(params.campus_id) ?? null;
  const [read, summaryRead, courses] = await Promise.all([
    tenantApiRead<InvoiceWire[]>(
      `/invoices?${invoiceListQuery(params, { outstanding: true })}`,
    ),
    tenantApiRead<FinanceSummaryWire>(
      isRecordId(campus)
        ? `/finance/summary?campus_id=${campus}`
        : "/finance/summary",
    ),
    courseFilterOptions(session),
  ]);
  const result = settle(read, OUTSTANDING_PATH);
  return (
    <>
      <SessionSync session={session} />
      <DataListTemplate
        title="Outstanding fees"
        description="Fee invoices with a balance still to collect, oldest due date first."
        breadcrumbs={BREADCRUMBS}
        toolbar={
          summaryRead.kind === "ok" ? (
            <SummaryStrip summary={summaryRead.data} />
          ) : result.kind === "ok" ? (
            <ReadErrorState
              title="The summary couldn't be loaded"
              reference={
                summaryRead.kind === "error" ? summaryRead.reference : null
              }
            />
          ) : null
        }
      >
        {result.kind === "ok" ? (
          <InvoiceList
            outstanding
            invoices={result.data}
            page={
              result.page ?? {
                limit: 25,
                offset: 0,
                total: result.data.length,
              }
            }
            campuses={sessionCampuses(session)}
            courses={courses}
            emptyState={{
              title: "Nothing outstanding",
              description:
                "Every live fee invoice at your campuses is paid. Unpaid and partly paid fee invoices appear here.",
            }}
          />
        ) : result.kind === "denied" ? (
          <ShellAccessDenied homeHref="/app" />
        ) : (
          <ReadErrorState
            title="Outstanding fees couldn't be loaded"
            reference={result.reference}
          />
        )}
      </DataListTemplate>
    </>
  );
}
