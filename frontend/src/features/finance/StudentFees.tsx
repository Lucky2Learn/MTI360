import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
} from "@/design-system/components";
import type { StudentWire } from "@/lib/api/admissions";
import type { InvoiceWire } from "@/lib/api/finance";

import { formatDate } from "../shared/format";
import { RecordLink } from "../shared/RecordLink";

import { Amount } from "./Amount";
import {
  INVOICE_STATUS_LABEL,
  INVOICE_STATUS_TONE,
  invoicePath,
  issuePath,
} from "./labels";

// ADM-12 Student 360 Fees (Phase 02-5; ADR-0022 addendum R2; readiness plan
// §4). The data is GET /invoices?student_id=… — the same list as FIN-04, so
// the tenant and the invoice's campus apply as everywhere; there is no
// student-fees route. Only fee invoices at the caller's campuses appear, and
// an empty list says nothing about other campuses. Actions by permission
// (UX only): raise a fee invoice for an admission without a live one, and
// record a payment on a fee invoice with a balance. Server-component
// compatible.

const LIVE = new Set<InvoiceWire["status"]>([
  "ISSUED",
  "PARTIALLY_PAID",
  "PAID",
]);

export type StudentFeesProps = {
  student: Pick<StudentWire, "id" | "admissions">;
  invoices: InvoiceWire[];
  canIssue: boolean;
  canRecord: boolean;
};

export function StudentFees({
  student,
  invoices,
  canIssue,
  canRecord,
}: StudentFeesProps) {
  const billed = new Set(
    invoices
      .filter((invoice) => LIVE.has(invoice.status))
      .map((invoice) => invoice.admission.id),
  );
  const unbilled = canIssue
    ? student.admissions.filter((admission) => !billed.has(admission.id))
    : [];
  return (
    <Card as="section">
      <CardHeader
        title="Fees"
        titleAs="h2"
        description="Fee invoices are not tax invoices."
      />
      <CardBody>
        <div className="flex flex-col gap-4">
          {invoices.length === 0 ? (
            <EmptyState
              title="No fee invoices"
              description="Fee invoices for this student's admissions at your campuses appear here."
            />
          ) : (
            <ul
              className="flex flex-col divide-y divide-border-subtle"
              aria-label="Fee invoices"
            >
              {invoices.map((invoice) => (
                <li
                  key={invoice.id}
                  className="flex flex-col gap-2 py-3 first:pt-0 last:pb-0 tablet:flex-row tablet:items-start tablet:justify-between tablet:gap-4"
                >
                  <span className="flex min-w-0 flex-col gap-1">
                    <span className="flex flex-wrap items-center gap-2 text-body-sm">
                      <RecordLink href={invoicePath(invoice.id)}>
                        {invoice.number}
                      </RecordLink>
                      <Badge tone={INVOICE_STATUS_TONE[invoice.status]}>
                        {INVOICE_STATUS_LABEL[invoice.status]}
                      </Badge>
                      {invoice.overdue && <Badge tone="error">Overdue</Badge>}
                    </span>
                    <span className="text-caption text-text-secondary">
                      {`${invoice.admission.number} · ${invoice.course.code} · due ${formatDate(invoice.due_date)}`}
                    </span>
                  </span>
                  <span className="flex flex-col gap-2 tablet:items-end">
                    <span className="text-body-sm text-text-primary">
                      <span className="text-text-secondary">Balance </span>
                      <Amount minor={invoice.balance_minor} strong />
                      <span className="text-text-secondary">
                        {" of "}
                        <Amount minor={invoice.total_minor} />
                      </span>
                    </span>
                    {canRecord &&
                      invoice.status !== "CANCELLED" &&
                      invoice.balance_minor > 0 && (
                        <Button
                          variant="secondary"
                          href={`${invoicePath(invoice.id)}?pay=1`}
                        >
                          {`Record payment on ${invoice.number}`}
                        </Button>
                      )}
                  </span>
                </li>
              ))}
            </ul>
          )}
          {unbilled.map((admission) => (
            <div
              key={admission.id}
              className="flex flex-col gap-2 tablet:flex-row tablet:items-center tablet:justify-between"
            >
              <span className="text-body-sm text-text-secondary">
                {`${admission.admission_number} · ${admission.course_code} has no fee invoice.`}
              </span>
              <Button href={issuePath(student.id, admission.id)}>
                {`Raise fee invoice for ${admission.admission_number}`}
              </Button>
            </div>
          ))}
        </div>
      </CardBody>
    </Card>
  );
}
