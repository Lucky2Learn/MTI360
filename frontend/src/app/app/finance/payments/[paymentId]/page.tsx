import {
  Alert,
  Badge,
  Card,
  CardBody,
  CardHeader,
} from "@/design-system/components";
import { DetailTemplate } from "@/design-system/templates/DetailTemplate";
import { Amount } from "@/features/finance/Amount";
import {
  INVOICE_READ,
  invoicePath,
  METHOD_LABEL,
  PAYMENT_STATUS_LABEL,
  PAYMENT_STATUS_TONE,
  paymentPath,
  PAYMENTS_PATH,
} from "@/features/finance/labels";
import {
  PaymentActions,
  RecorderNotice,
} from "@/features/finance/PaymentActions";
import { Term } from "@/features/finance/Term";
import { formatDate, formatDateTime } from "@/features/shared/format";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
import { RecordLink } from "@/features/shared/RecordLink";
import type { PaymentWire } from "@/lib/api/finance";
import { tenantApiRead } from "@/lib/api/server-read";
import {
  requireRecordId,
  settle,
  tenantPageAccess,
} from "@/lib/session/page-access";
import { SessionSync } from "@/lib/session/SessionProvider";
import { PageContainer, ShellAccessDenied } from "@/shells";

import type { Metadata } from "next";

// FIN-07 Payment, /app/finance/payments/[paymentId] (Phase 02-5; ADR-0022 §4,
// §9; readiness plan §4). Another tenant's or campus's payment, or a
// malformed ID, is RESOURCE-02. The status says what the payment did to the
// balance; the actions follow it (PaymentActions) and the API decides.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Payment · Tenant Application · MTI 360",
};

type Props = { params: Promise<{ paymentId: string }> };

const EFFECT: Record<PaymentWire["status"], string> = {
  PENDING:
    "Awaiting clearance: not yet in the balance and no receipt. Confirm it once the bank credits the money, or mark it as failed.",
  CONFIRMED: "Counted in the fee invoice's balance.",
  FAILED: "Not honoured: never counted in the balance and no receipt.",
  REVERSED:
    "Reversed: taken back out of the balance. The receipt stays on record, shown as cancelled.",
};

export default async function PaymentPage({ params }: Props) {
  const id = requireRecordId((await params).paymentId);
  const path = paymentPath(id);
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
    await tenantApiRead<PaymentWire>(`/payments/${id}`),
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
              title="This payment couldn't be loaded"
              reference={result.reference}
            />
          </PageContainer>
        )}
      </>
    );
  }
  const payment = result.data;
  const title = `${METHOD_LABEL[payment.method]} payment`;
  return (
    <>
      <SessionSync session={session} />
      <DetailTemplate
        title={title}
        description={`${payment.student.full_name} · ${payment.student.number} · ${payment.invoice.number}`}
        breadcrumbs={[
          { label: "Finance" },
          { label: "Payments", href: PAYMENTS_PATH },
          {
            label: `${METHOD_LABEL[payment.method]} · ${formatDate(payment.received_on)}`,
          },
        ]}
        status={
          <Badge tone={PAYMENT_STATUS_TONE[payment.status]}>
            {PAYMENT_STATUS_LABEL[payment.status]}
          </Badge>
        }
        actions={<PaymentActions payment={payment} />}
        asideLabel="Receipt"
        main={
          <Card as="section">
            <CardHeader title="Payment" titleAs="h2" />
            <CardBody>
              <div className="flex flex-col gap-4">
                <p className="text-section text-text-primary">
                  <Amount minor={payment.amount_minor} />
                </p>
                <Alert
                  tone={payment.status === "PENDING" ? "warning" : "info"}
                  title={PAYMENT_STATUS_LABEL[payment.status]}
                >
                  {EFFECT[payment.status]}
                  {payment.status_reason
                    ? ` Reason: ${payment.status_reason}`
                    : ""}
                </Alert>
                <RecorderNotice payment={payment} />
                <dl className="flex flex-col gap-4">
                  <Term term="Fee invoice">
                    <RecordLink href={invoicePath(payment.invoice.id)}>
                      {payment.invoice.number}
                    </RecordLink>
                  </Term>
                  <Term term="Student">
                    {`${payment.student.full_name} · ${payment.student.number}`}
                  </Term>
                  <Term term="Method">{METHOD_LABEL[payment.method]}</Term>
                  <Term term="Reference">{payment.reference ?? "None"}</Term>
                  <Term term="Received on">
                    {formatDate(payment.received_on)}
                  </Term>
                  <Term term="Recorded">
                    {`${formatDateTime(payment.recorded_at)}${payment.recorded_by ? ` · ${payment.recorded_by}` : ""}`}
                  </Term>
                  {payment.confirmed_at && (
                    <Term term="Confirmed">
                      {formatDateTime(payment.confirmed_at)}
                    </Term>
                  )}
                  {payment.closed_at && (
                    <Term
                      term={payment.status === "FAILED" ? "Failed" : "Reversed"}
                    >
                      {formatDateTime(payment.closed_at)}
                    </Term>
                  )}
                </dl>
              </div>
            </CardBody>
          </Card>
        }
        aside={
          <Card as="section">
            <CardHeader title="Receipt" titleAs="h2" />
            <CardBody>
              {payment.receipt ? (
                <dl className="flex flex-col gap-4">
                  <Term term="Number">
                    {payment.receipt.cancelled
                      ? `${payment.receipt.number} (cancelled)`
                      : payment.receipt.number}
                  </Term>
                  <Term term="Issued">
                    {formatDateTime(payment.receipt.issued_at)}
                  </Term>
                </dl>
              ) : (
                <p className="text-body-sm text-text-secondary">
                  {payment.status === "PENDING"
                    ? "A receipt is issued when the payment is confirmed as cleared."
                    : "No receipt was issued for this payment."}
                </p>
              )}
            </CardBody>
          </Card>
        }
      />
    </>
  );
}
