import { Button } from "@/design-system/components";
import { DataListTemplate } from "@/design-system/templates/DataListTemplate";
import { STUDENT_READ, STUDENTS_PATH } from "@/features/applications/labels";
import { InvoiceList } from "@/features/finance/InvoiceList";
import {
  INVOICE_ISSUE,
  INVOICE_READ,
  INVOICES_PATH,
} from "@/features/finance/labels";
import { invoiceListQuery, type SearchParams } from "@/features/finance/query";
import {
  courseFilterOptions,
  sessionCampuses,
} from "@/features/finance/server";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import type { InvoiceWire } from "@/lib/api/finance";
import { tenantApiRead } from "@/lib/api/server-read";
import { can } from "@/lib/authz/requirements";
import { settle, tenantPageAccess } from "@/lib/session/page-access";
import { SessionSync } from "@/lib/session/SessionProvider";
import { ShellAccessDenied } from "@/shells";

import type { Metadata } from "next";

// FIN-04 Fee invoices, /app/finance/invoices (Phase 02-5; readiness plan §4).
// Gate: ready session → invoice.read (AUTHZ-01 otherwise) → the list read on
// the server with the tenant cookie only; the API filters by tenant and the
// caller's campuses. A fee invoice is raised from an admitted student's
// profile (the admission is the billing context), so "Raise fee invoice"
// leads to Students for members who may read them.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Fee invoices · Tenant Application · MTI 360",
};

const BREADCRUMBS = [{ label: "Finance" }, { label: "Fee invoices" }];

export default async function InvoicesPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const { session, allowed } = await tenantPageAccess(
    INVOICES_PATH,
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
  const query = invoiceListQuery(await searchParams);
  const [read, courses] = await Promise.all([
    tenantApiRead<InvoiceWire[]>(`/invoices?${query}`),
    courseFilterOptions(session),
  ]);
  const result = settle(read, INVOICES_PATH);
  const canRaise =
    can(session.permissions, INVOICE_ISSUE) &&
    can(session.permissions, STUDENT_READ);
  const raise = canRaise ? (
    <Button href={STUDENTS_PATH} variant="secondary">
      Raise fee invoice
    </Button>
  ) : null;
  return (
    <>
      <SessionSync session={session} />
      <DataListTemplate
        title="Fee invoices"
        description="Fee invoices of admitted students at your campuses. Fee invoices are not tax invoices."
        breadcrumbs={BREADCRUMBS}
        actions={raise}
      >
        {result.kind === "ok" ? (
          <InvoiceList
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
              title: "No fee invoices yet",
              description: canRaise
                ? "Fee invoices are raised from an admitted student's profile: open the student and choose Raise fee invoice."
                : "Fee invoices are raised for admitted students. They appear here once your finance team issues them.",
              action: raise ?? undefined,
            }}
          />
        ) : result.kind === "denied" ? (
          <ShellAccessDenied homeHref="/app" />
        ) : (
          <ReadErrorState
            title="Fee invoices couldn't be loaded"
            reference={result.reference}
          />
        )}
      </DataListTemplate>
    </>
  );
}
