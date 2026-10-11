import {
  Badge,
  EmptyState,
  Timeline,
  type TimelineItem,
  type Tone,
} from "@/design-system/components";
import type {
  FinanceActivityWire,
  InvoiceDetailWire,
  PaymentWire,
} from "@/lib/api/finance";

import { formatDate, formatDateTime } from "../shared/format";
import { RecordLink } from "../shared/RecordLink";

import { Amount } from "./Amount";
import {
  ACTIVITY_LABEL,
  METHOD_LABEL,
  PAYMENT_STATUS_LABEL,
  PAYMENT_STATUS_TONE,
  paymentPath,
  receiptPath,
} from "./labels";
import { formatPaise } from "./money";

// FIN-05 fee invoice sections (Phase 02-5; ADR-0022 §5, §7; readiness plan
// §4): the issued lines (with the fee structure's amount beside an adjusted
// line), the balance, the payments and the history. Every number is the
// server's; nothing is summed here. Server-component compatible, and reused
// by the print view.

const cell = "py-2 align-top";

/** `plain`: text instead of badges (print views: paper drops backgrounds). */
export function InvoiceLines({
  invoice,
  plain = false,
}: {
  invoice: InvoiceDetailWire;
  plain?: boolean;
}) {
  const showStructure = invoice.adjusted;
  return (
    <table className="w-full text-body-sm">
      <caption className="sr-only">Fee heads and amounts</caption>
      <thead>
        <tr className="border-b border-border-subtle text-left text-text-secondary">
          <th scope="col" className={`${cell} font-medium`}>
            Fee head
          </th>
          {showStructure && (
            <th scope="col" className={`${cell} text-right font-medium`}>
              Fee structure
            </th>
          )}
          <th scope="col" className={`${cell} text-right font-medium`}>
            Amount
          </th>
        </tr>
      </thead>
      <tbody>
        {invoice.lines.map((line) => (
          <tr key={line.position} className="border-b border-border-subtle">
            <th
              scope="row"
              className={`${cell} text-left font-normal text-text-primary`}
            >
              <span className="flex flex-wrap items-center gap-2">
                {line.fee_head}
                {line.adjusted &&
                  (plain ? (
                    <span className="text-text-secondary">
                      {line.structure_amount_minor === null
                        ? "(added)"
                        : "(adjusted)"}
                    </span>
                  ) : (
                    <Badge tone="warning">
                      {line.structure_amount_minor === null
                        ? "Added"
                        : "Adjusted"}
                    </Badge>
                  ))}
              </span>
            </th>
            {showStructure && (
              <td className={`${cell} text-right text-text-secondary`}>
                {line.structure_amount_minor === null ? (
                  "—"
                ) : (
                  <Amount minor={line.structure_amount_minor} />
                )}
              </td>
            )}
            <td className={`${cell} text-right text-text-primary`}>
              <Amount minor={line.amount_minor} />
            </td>
          </tr>
        ))}
      </tbody>
      <tfoot>
        {showStructure && (
          <tr>
            <th
              scope="row"
              colSpan={2}
              className="pt-3 text-left font-normal text-text-secondary"
            >
              Fee structure total
            </th>
            <td className="pt-3 text-right text-text-secondary">
              <Amount minor={invoice.structure_total_minor} />
            </td>
          </tr>
        )}
        <tr>
          <th
            scope="row"
            colSpan={showStructure ? 2 : 1}
            className="pt-3 text-left font-medium text-text-primary"
          >
            Total
          </th>
          <td className="pt-3 text-right text-text-primary">
            <Amount minor={invoice.total_minor} strong />
          </td>
        </tr>
      </tfoot>
    </table>
  );
}

/** Paid, balance and (when any) cheques or drafts awaiting clearance. */
export function InvoiceBalance({ invoice }: { invoice: InvoiceDetailWire }) {
  const cancelled = invoice.status === "CANCELLED";
  return (
    <dl className="flex flex-col gap-3 text-body-sm">
      <div className="flex justify-between gap-4">
        <dt className="text-text-secondary">Total</dt>
        <dd className="text-text-primary">
          <Amount minor={invoice.total_minor} />
        </dd>
      </div>
      <div className="flex justify-between gap-4">
        <dt className="text-text-secondary">Paid</dt>
        <dd className="text-text-primary">
          <Amount minor={invoice.paid_minor} />
        </dd>
      </div>
      {invoice.pending_minor > 0 && (
        <div className="flex justify-between gap-4">
          <dt className="text-text-secondary">Awaiting clearance</dt>
          <dd className="text-text-primary">
            <Amount minor={invoice.pending_minor} />
          </dd>
        </div>
      )}
      <div className="flex justify-between gap-4 border-t border-border-subtle pt-3">
        <dt className="font-medium text-text-primary">
          {cancelled ? "Balance (cancelled)" : "Balance"}
        </dt>
        <dd className="text-text-primary">
          <Amount minor={invoice.balance_minor} strong />
        </dd>
      </div>
    </dl>
  );
}

export function paymentSummary(payment: PaymentWire): string {
  return `${METHOD_LABEL[payment.method]} ${formatPaise(payment.amount_minor)} received ${formatDate(payment.received_on)}`;
}

export function InvoicePayments({ payments }: { payments: PaymentWire[] }) {
  if (payments.length === 0) {
    return (
      <EmptyState
        title="No payments yet"
        description="Payments recorded against this fee invoice appear here. Cash, UPI and bank transfers count at once; a cheque or demand draft counts once it clears."
      />
    );
  }
  return (
    <ul
      className="flex flex-col divide-y divide-border-subtle"
      aria-label="Payments"
    >
      {payments.map((payment) => (
        <li
          key={payment.id}
          className="flex flex-col gap-1 py-3 first:pt-0 last:pb-0 tablet:flex-row tablet:items-start tablet:justify-between tablet:gap-4"
        >
          <span className="flex min-w-0 flex-col gap-1">
            <span className="flex flex-wrap items-center gap-2 text-body-sm text-text-primary">
              <RecordLink href={paymentPath(payment.id)}>
                {`${METHOD_LABEL[payment.method]} · ${formatDate(payment.received_on)}`}
              </RecordLink>
              <Badge tone={PAYMENT_STATUS_TONE[payment.status]}>
                {PAYMENT_STATUS_LABEL[payment.status]}
              </Badge>
            </span>
            <span className="text-caption text-text-secondary">
              {payment.receipt ? (
                <RecordLink href={receiptPath(payment.id)}>
                  {payment.receipt.cancelled
                    ? `Receipt ${payment.receipt.number} (cancelled)`
                    : `Receipt ${payment.receipt.number}`}
                </RecordLink>
              ) : payment.status === "PENDING" ? (
                "No receipt until it clears"
              ) : (
                "No receipt"
              )}
            </span>
          </span>
          <span className="text-body-sm text-text-primary tablet:text-right">
            <Amount minor={payment.amount_minor} strong />
          </span>
        </li>
      ))}
    </ul>
  );
}

const ACTIVITY_TONE: Record<FinanceActivityWire["kind"], Tone> = {
  ISSUED: "info",
  CANCELLED: "neutral",
  PAYMENT_RECORDED: "success",
  PAYMENT_CONFIRMED: "success",
  PAYMENT_FAILED: "error",
  PAYMENT_REVERSED: "warning",
};

function text(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function amount(value: unknown): string | null {
  return typeof value === "number" && Number.isSafeInteger(value)
    ? formatPaise(value)
    : null;
}

function activityDescription(item: FinanceActivityWire): string | null {
  const details = item.details;
  const parts = [
    amount(details.amount_minor) ?? amount(details.total_minor),
    text(details.receipt_number)
      ? `Receipt ${text(details.receipt_number)}`
      : null,
    item.kind === "PAYMENT_RECORDED" && details.status === "PENDING"
      ? "awaiting clearance"
      : null,
  ].filter(Boolean);
  const reason = text(details.reason);
  return (
    [parts.join(" · "), reason ? `Reason: ${reason}` : null]
      .filter(Boolean)
      .join("\n") || null
  );
}

export function InvoiceActivity({
  activity,
}: {
  activity: FinanceActivityWire[];
}) {
  const items: TimelineItem[] = activity.map((item) => {
    const description = activityDescription(item);
    return {
      id: item.id,
      title: ACTIVITY_LABEL[item.kind],
      timestamp: item.created_at,
      timestampLabel: formatDateTime(item.created_at),
      actor: item.actor ?? undefined,
      description: description ? (
        <p className="whitespace-pre-wrap break-words text-body-sm text-text-primary">
          {description}
        </p>
      ) : undefined,
      tone: ACTIVITY_TONE[item.kind],
    };
  });
  return <Timeline items={items} aria-label="Fee invoice history" />;
}
