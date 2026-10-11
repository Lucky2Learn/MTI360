import {
  InvoiceBalance,
  InvoiceLines,
} from "@/features/finance/InvoiceSections";
import {
  INVOICE_READ,
  INVOICE_STATUS_LABEL,
  invoicePath,
  NON_TAX_LABEL,
} from "@/features/finance/labels";
import { PrintTerm, PrintView } from "@/features/finance/PrintView";
import { formatDate } from "@/features/shared/format";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import type { InvoiceDetailWire } from "@/lib/api/finance";
import { tenantApiRead } from "@/lib/api/server-read";
import {
  requireRecordId,
  settle,
  tenantPageAccess,
} from "@/lib/session/page-access";
import { SessionSync } from "@/lib/session/SessionProvider";
import { PageContainer, ShellAccessDenied } from "@/shells";

import type { Metadata } from "next";

// FIN-05 print view, /app/finance/invoices/[invoiceId]/print (Phase 02-5;
// ADR-0022 §2; readiness plan §4). The same read and gate as the detail
// page; the institute's name comes from the session, never from code. Every
// print says "Fee invoice — not a tax invoice". Single column on paper.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Print fee invoice · Tenant Application · MTI 360",
};

type Props = { params: Promise<{ invoiceId: string }> };

export default async function PrintInvoicePage({ params }: Props) {
  const id = requireRecordId((await params).invoiceId);
  const path = `${invoicePath(id)}/print`;
  const { session, allowed } = await tenantPageAccess(path, INVOICE_READ);
  if (!allowed) {
    return (
      <>
        <SessionSync session={session} />
        <ShellAccessDenied homeHref="/app" />
      </>
    );
  }
  const result = settle(
    await tenantApiRead<InvoiceDetailWire>(`/invoices/${id}`),
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
              title="This fee invoice couldn't be loaded"
              reference={result.reference}
            />
          </PageContainer>
        )}
      </>
    );
  }
  const invoice = result.data;
  const status =
    invoice.status === "CANCELLED"
      ? `Cancelled${invoice.status_reason ? ` — ${invoice.status_reason}` : ""}`
      : `${INVOICE_STATUS_LABEL[invoice.status]}${invoice.overdue ? " · Overdue" : ""}`;
  return (
    <>
      <SessionSync session={session} />
      <PageContainer width="standard">
        <PrintView
          backHref={invoicePath(invoice.id)}
          backLabel="Back to fee invoice"
          printLabel="Print fee invoice"
        >
          <header className="flex flex-col gap-1 border-b border-border-subtle pb-4">
            <p className="text-body-sm text-text-secondary">
              {session.active_institute?.name ?? ""}
            </p>
            <h1 className="text-section text-text-primary">
              {`Fee invoice ${invoice.number}`}
            </h1>
            <p className="text-body-sm font-medium text-text-primary">
              {NON_TAX_LABEL}
            </p>
          </header>
          <dl className="grid grid-cols-1 gap-4 tablet:grid-cols-2 print:grid-cols-2">
            <PrintTerm term="Student">
              {`${invoice.student.full_name} · ${invoice.student.number}`}
            </PrintTerm>
            <PrintTerm term="Admission">{invoice.admission.number}</PrintTerm>
            <PrintTerm term="Course">
              {`${invoice.course.code} · ${invoice.course.name}`}
            </PrintTerm>
            <PrintTerm term="Campus">{invoice.campus.code}</PrintTerm>
            <PrintTerm term="Issued">{formatDate(invoice.issued_at)}</PrintTerm>
            <PrintTerm term="Due date">
              {formatDate(invoice.due_date)}
            </PrintTerm>
            <PrintTerm term="Status">{status}</PrintTerm>
          </dl>
          <InvoiceLines invoice={invoice} plain />
          {invoice.adjusted && invoice.adjustment_reason && (
            <p className="text-body-sm whitespace-pre-wrap break-words text-text-secondary">
              {`Adjusted from the fee structure: ${invoice.adjustment_reason}`}
            </p>
          )}
          <div className="tablet:ml-auto tablet:w-80 print:ml-auto print:w-80">
            <InvoiceBalance invoice={invoice} />
          </div>
        </PrintView>
      </PageContainer>
    </>
  );
}
