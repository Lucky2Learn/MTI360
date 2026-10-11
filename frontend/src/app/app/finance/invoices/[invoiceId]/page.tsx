import {
  Alert,
  Badge,
  Card,
  CardBody,
  CardHeader,
} from "@/design-system/components";
import { DetailTemplate } from "@/design-system/templates/DetailTemplate";
import { STUDENT_READ, studentPath } from "@/features/applications/labels";
import { first } from "@/features/courses/query";
import { InvoiceActions } from "@/features/finance/InvoiceActions";
import {
  InvoiceActivity,
  InvoiceBalance,
  InvoiceLines,
  InvoicePayments,
} from "@/features/finance/InvoiceSections";
import {
  FEE_STRUCTURE_READ,
  INVOICE_READ,
  INVOICE_STATUS_LABEL,
  INVOICE_STATUS_TONE,
  INVOICES_PATH,
  invoicePath,
  NON_TAX_LABEL,
  structurePath,
} from "@/features/finance/labels";
import type { SearchParams } from "@/features/finance/query";
import { Term } from "@/features/finance/Term";
import { formatDate, formatDateTime } from "@/features/shared/format";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import { RecordLink } from "@/features/shared/RecordLink";
import type { InvoiceDetailWire } from "@/lib/api/finance";
import { tenantApiRead } from "@/lib/api/server-read";
import { can } from "@/lib/authz/requirements";
import {
  requireRecordId,
  settle,
  tenantPageAccess,
} from "@/lib/session/page-access";
import { SessionSync } from "@/lib/session/SessionProvider";
import { PageContainer, ShellAccessDenied } from "@/shells";

import type { Metadata } from "next";

// FIN-05 Fee invoice, /app/finance/invoices/[invoiceId] (Phase 02-5;
// ADR-0022; readiness plan §4). Another tenant's or another campus's fee
// invoice, or a malformed ID, is RESOURCE-02 (the API answers 404 for all of
// them). Every amount and status is the server's. Links to the student and
// the fee structure appear only for members who may open them.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Fee invoice · Tenant Application · MTI 360",
};

type Props = {
  params: Promise<{ invoiceId: string }>;
  searchParams: Promise<SearchParams>;
};

export default async function InvoicePage({ params, searchParams }: Props) {
  const id = requireRecordId((await params).invoiceId);
  const path = invoicePath(id);
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
  const openPayment = first((await searchParams).pay) === "1";
  const readsStudents = can(session.permissions, STUDENT_READ);
  const readsStructures = can(session.permissions, FEE_STRUCTURE_READ);
  return (
    <>
      <SessionSync session={session} />
      <DetailTemplate
        title={invoice.number}
        description={`${invoice.student.full_name} · ${invoice.student.number} · ${invoice.course.code} · ${invoice.campus.code}`}
        breadcrumbs={[
          { label: "Finance" },
          { label: "Fee invoices", href: INVOICES_PATH },
          { label: invoice.number },
        ]}
        status={
          <span className="flex flex-wrap gap-2">
            <Badge tone={INVOICE_STATUS_TONE[invoice.status]}>
              {INVOICE_STATUS_LABEL[invoice.status]}
            </Badge>
            {invoice.overdue && <Badge tone="error">Overdue</Badge>}
          </span>
        }
        actions={<InvoiceActions invoice={invoice} openPayment={openPayment} />}
        asideLabel="Balance and details"
        main={
          <>
            {invoice.status === "CANCELLED" && (
              <Alert tone="warning" title="This fee invoice is cancelled">
                {invoice.status_reason
                  ? `Reason: ${invoice.status_reason}`
                  : "It stays in the history and can't be paid."}
              </Alert>
            )}
            <Card as="section">
              <CardHeader
                title="Fee heads"
                titleAs="h2"
                description={NON_TAX_LABEL}
              />
              <CardBody>
                <div className="flex flex-col gap-4">
                  <InvoiceLines invoice={invoice} />
                  {invoice.adjusted && invoice.adjustment_reason && (
                    <p className="text-body-sm whitespace-pre-wrap break-words text-text-secondary">
                      {`Adjusted from the fee structure: ${invoice.adjustment_reason}`}
                    </p>
                  )}
                </div>
              </CardBody>
            </Card>
            <Card as="section">
              <CardHeader title="Payments" titleAs="h2" />
              <CardBody>
                <InvoicePayments payments={invoice.payments} />
              </CardBody>
            </Card>
          </>
        }
        aside={
          <>
            <Card as="section">
              <CardHeader title="Balance" titleAs="h2" />
              <CardBody>
                <InvoiceBalance invoice={invoice} />
              </CardBody>
            </Card>
            <Card as="section">
              <CardHeader title="Details" titleAs="h2" />
              <CardBody>
                <dl className="flex flex-col gap-4">
                  <Term term="Student">
                    {readsStudents ? (
                      <RecordLink href={studentPath(invoice.student.id)}>
                        {`${invoice.student.full_name} · ${invoice.student.number}`}
                      </RecordLink>
                    ) : (
                      `${invoice.student.full_name} · ${invoice.student.number}`
                    )}
                  </Term>
                  <Term term="Admission">{invoice.admission.number}</Term>
                  <Term term="Course">
                    {`${invoice.course.code} · ${invoice.course.name}`}
                  </Term>
                  <Term term="Campus">{invoice.campus.code}</Term>
                  <Term term="Due date">{formatDate(invoice.due_date)}</Term>
                  <Term term="Issued">{formatDateTime(invoice.issued_at)}</Term>
                  <Term term="Fee structure">
                    {readsStructures ? (
                      <RecordLink
                        href={structurePath(invoice.fee_structure.id)}
                      >
                        {invoice.fee_structure.name}
                      </RecordLink>
                    ) : (
                      invoice.fee_structure.name
                    )}
                  </Term>
                  {invoice.cancelled_at && (
                    <Term term="Cancelled">
                      {formatDateTime(invoice.cancelled_at)}
                    </Term>
                  )}
                </dl>
              </CardBody>
            </Card>
          </>
        }
      >
        <Card as="section">
          <CardHeader title="History" titleAs="h2" />
          <CardBody>
            <InvoiceActivity activity={invoice.activity} />
          </CardBody>
        </Card>
      </DetailTemplate>
    </>
  );
}
