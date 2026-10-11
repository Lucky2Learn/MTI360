import { EmptyState, Button } from "@/design-system/components";
import { Amount } from "@/features/finance/Amount";
import {
  INVOICE_READ,
  METHOD_LABEL,
  paymentPath,
  receiptPath,
} from "@/features/finance/labels";
import { PrintTerm, PrintView } from "@/features/finance/PrintView";
import { formatDate, formatDateTime } from "@/features/shared/format";
import { ReadErrorState } from "@/features/shared/ReadErrorState";
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

// FIN-07 Receipt, /app/finance/payments/[paymentId]/receipt (Phase 02-5;
// ADR-0022 §3, §4; readiness plan §4). A confirmed payment's receipt, ready
// to print; a reversed payment's receipt prints as CANCELLED. A payment
// without a receipt (awaiting clearance or failed) explains why. The
// institute's name comes from the session.
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Receipt · Tenant Application · MTI 360",
};

type Props = { params: Promise<{ paymentId: string }> };

export default async function ReceiptPage({ params }: Props) {
  const id = requireRecordId((await params).paymentId);
  const path = receiptPath(id);
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
              title="This receipt couldn't be loaded"
              reference={result.reference}
            />
          </PageContainer>
        )}
      </>
    );
  }
  const payment = result.data;
  const receipt = payment.receipt;
  return (
    <>
      <SessionSync session={session} />
      <PageContainer width="standard">
        {receipt === null ? (
          <EmptyState
            title="No receipt for this payment"
            titleAs="h1"
            description={
              payment.status === "PENDING"
                ? "A receipt is issued when the cheque or demand draft is confirmed as cleared."
                : "Only a confirmed payment has a receipt."
            }
            primaryAction={
              <Button variant="secondary" href={paymentPath(payment.id)}>
                Back to payment
              </Button>
            }
          />
        ) : (
          <PrintView
            backHref={paymentPath(payment.id)}
            backLabel="Back to payment"
            printLabel="Print receipt"
          >
            <header className="flex flex-col gap-1 border-b border-border-subtle pb-4">
              <p className="text-body-sm text-text-secondary">
                {session.active_institute?.name ?? ""}
              </p>
              <h1 className="text-section text-text-primary">
                {`Receipt ${receipt.number}`}
              </h1>
              <p className="text-body-sm text-text-secondary">
                Fee receipt — not a tax invoice
              </p>
              {receipt.cancelled && (
                <p className="text-body font-semibold text-text-primary">
                  CANCELLED — this payment was reversed
                  {payment.status_reason ? `: ${payment.status_reason}` : ""}
                </p>
              )}
            </header>
            <p className="text-body text-text-primary">
              {"Received with thanks "}
              <Amount minor={payment.amount_minor} strong />
              {` from ${payment.student.full_name} (${payment.student.number}) towards fee invoice ${payment.invoice.number}.`}
            </p>
            <dl className="grid grid-cols-1 gap-4 tablet:grid-cols-2 print:grid-cols-2">
              <PrintTerm term="Method">
                {METHOD_LABEL[payment.method]}
              </PrintTerm>
              <PrintTerm term="Reference">
                {payment.reference ?? "None"}
              </PrintTerm>
              <PrintTerm term="Received on">
                {formatDate(payment.received_on)}
              </PrintTerm>
              <PrintTerm term="Receipt issued">
                {formatDateTime(receipt.issued_at)}
              </PrintTerm>
              {payment.recorded_by && (
                <PrintTerm term="Recorded by">{payment.recorded_by}</PrintTerm>
              )}
            </dl>
          </PrintView>
        )}
      </PageContainer>
    </>
  );
}
