"use client";

import {
  Badge,
  Button,
  DataTable,
  DatePicker,
  FilterBar,
  Pagination,
  Search,
  Select,
  type DataTableColumn,
} from "@/design-system/components";
import type {
  PaymentMethod,
  PaymentStatus,
  PaymentWire,
} from "@/lib/api/finance";
import type { PageMeta } from "@/lib/api/server-read";
import type { CampusWire } from "@/lib/api/types";
import { useListParams } from "@/lib/navigation/list-params";

import { formatDate } from "../shared/format";
import { RecordLink } from "../shared/RecordLink";

import { Amount } from "./Amount";
import {
  METHOD_LABEL,
  PAYMENT_STATUS_LABEL,
  PAYMENT_STATUS_TONE,
  paymentPath,
} from "./labels";

// FIN-06 Payments (Phase 02-5; readiness plan §4): every offline payment at
// the caller's campuses (the API scopes the rows), with its status and
// receipt. Filters live in the URL; "Awaiting clearance" is the queue of
// cheques and demand drafts to confirm or fail.

const ANY = "any";
const STATUSES: PaymentStatus[] = [
  "PENDING",
  "CONFIRMED",
  "FAILED",
  "REVERSED",
];
const METHODS: PaymentMethod[] = [
  "CASH",
  "UPI",
  "BANK_TRANSFER",
  "CHEQUE",
  "DEMAND_DRAFT",
];

export function PaymentList({
  payments,
  page,
  campuses,
}: {
  payments: PaymentWire[];
  page: PageMeta;
  campuses: CampusWire[];
}) {
  const params = useListParams();
  const q = params.get("q") ?? "";
  const status = params.get("status");
  const method = params.get("method");
  const campus = params.get("campus_id");
  const from = params.get("received_from");
  const to = params.get("received_to");
  const active = [status, method, campus, from, to].filter(Boolean).length;
  const filtered = Boolean(q) || active > 0;
  const clearAll = {
    q: null,
    status: null,
    method: null,
    campus_id: null,
    received_from: null,
    received_to: null,
  };

  const columns: DataTableColumn<PaymentWire>[] = [
    {
      id: "payment",
      header: "Payment",
      isRowHeader: true,
      cell: (payment) => (
        <RecordLink href={paymentPath(payment.id)}>
          {`${METHOD_LABEL[payment.method]} · ${formatDate(payment.received_on)}`}
        </RecordLink>
      ),
    },
    {
      id: "student",
      header: "Student",
      cell: (payment) => (
        <span className="flex flex-col">
          <span>{payment.student.full_name}</span>
          <span className="text-caption text-text-secondary">
            {payment.invoice.number}
          </span>
        </span>
      ),
    },
    {
      id: "receipt",
      header: "Receipt",
      visibleFrom: "desktop",
      cell: (payment) =>
        payment.receipt
          ? `${payment.receipt.number}${payment.receipt.cancelled ? " (cancelled)" : ""}`
          : "—",
    },
    {
      id: "amount",
      header: "Amount",
      align: "end",
      cell: (payment) => <Amount minor={payment.amount_minor} strong />,
    },
    {
      id: "status",
      header: "Status",
      cell: (payment) => (
        <Badge tone={PAYMENT_STATUS_TONE[payment.status]}>
          {PAYMENT_STATUS_LABEL[payment.status]}
        </Badge>
      ),
    },
  ];

  return (
    <div className="flex min-w-0 flex-col gap-4">
      <FilterBar
        label="Payment filters"
        search={
          <Search
            label="Search payments"
            isLabelHidden
            placeholder="Invoice, receipt or student number, name or reference"
            defaultValue={q}
            onSubmit={(value) => params.set({ q: value.trim() || null })}
            onClear={() => params.set({ q: null })}
          />
        }
        activeFilterCount={active}
        resultCount={`${page.total} ${page.total === 1 ? "payment" : "payments"}`}
        onClear={() => params.set({ ...clearAll, q: q || null })}
        filters={
          <>
            <Select
              label="Status"
              options={[
                { id: ANY, label: "Any status" },
                ...STATUSES.map((value) => ({
                  id: value,
                  label: PAYMENT_STATUS_LABEL[value],
                })),
              ]}
              value={status ?? ANY}
              onChange={(value) =>
                params.set({ status: value === ANY ? null : value })
              }
            />
            <Select
              label="Method"
              options={[
                { id: ANY, label: "Any method" },
                ...METHODS.map((value) => ({
                  id: value,
                  label: METHOD_LABEL[value],
                })),
              ]}
              value={method ?? ANY}
              onChange={(value) =>
                params.set({ method: value === ANY ? null : value })
              }
            />
            {campuses.length > 1 && (
              <Select
                label="Campus"
                options={[
                  { id: ANY, label: "All my campuses" },
                  ...campuses.map((item) => ({
                    id: item.id,
                    label: `${item.code} · ${item.name}`,
                  })),
                ]}
                value={campus ?? ANY}
                onChange={(value) =>
                  params.set({ campus_id: value === ANY ? null : value })
                }
              />
            )}
            <DatePicker
              label="Received from"
              value={from}
              onChange={(iso) => params.set({ received_from: iso })}
            />
            <DatePicker
              label="Received to"
              value={to}
              minValue={from ?? undefined}
              onChange={(iso) => params.set({ received_to: iso })}
            />
          </>
        }
      />
      <DataTable
        label="Payments"
        columns={columns}
        rows={payments}
        getRowId={(payment) => payment.id}
        getRowLabel={(payment) =>
          `${METHOD_LABEL[payment.method]} ${payment.invoice.number}`
        }
        mobileLayout="cards"
        emptyState={
          filtered
            ? {
                title: "No payments match these filters",
                description: "Try another search term or clear the filters.",
                action: (
                  <Button
                    variant="secondary"
                    onPress={() => params.set(clearAll)}
                  >
                    Clear filters
                  </Button>
                ),
              }
            : {
                title: "No payments yet",
                description:
                  "Payments are recorded on a fee invoice. Cash, UPI and bank transfers get a receipt at once; cheques and demand drafts wait here until they clear.",
              }
        }
        footer={
          page.total > page.limit ? (
            <Pagination
              label="Payment pages"
              itemLabel="payments"
              page={Math.floor(page.offset / page.limit) + 1}
              pageSize={page.limit}
              totalItems={page.total}
              onPageChange={(next) =>
                params.set(
                  {
                    offset: next > 1 ? String((next - 1) * page.limit) : null,
                  },
                  { keepPage: true },
                )
              }
            />
          ) : undefined
        }
      />
    </div>
  );
}
