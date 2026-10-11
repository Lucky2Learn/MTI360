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
import type { InvoiceWire } from "@/lib/api/finance";
import type { PageMeta } from "@/lib/api/server-read";
import type { CampusWire } from "@/lib/api/types";
import { useListParams } from "@/lib/navigation/list-params";

import { formatDate } from "../shared/format";
import { RecordLink } from "../shared/RecordLink";

import { Amount } from "./Amount";
import {
  INVOICE_STATUS_LABEL,
  INVOICE_STATUS_TONE,
  invoicePath,
} from "./labels";

import type { ReactNode } from "react";

// FIN-04 Fee invoices and FIN-08 Outstanding (Phase 02-5; readiness plan
// §4): one list, two views. Filters live in the URL and the server renders
// the page; the API applies the tenant and the caller's campuses to every
// row, so a campus filter only narrows what the caller may already see.
// Overdue is the server's flag (unpaid and past due in IST). Status is
// always a text badge; amounts are exact paise, right-aligned.

const ANY = "any";

export type FilterOption = { id: string; label: string };

function campusOptions(campuses: CampusWire[]): FilterOption[] {
  return campuses.map((campus) => ({
    id: campus.id,
    label: `${campus.code} · ${campus.name}`,
  }));
}

export function InvoiceList({
  invoices,
  page,
  campuses,
  courses,
  outstanding = false,
  emptyState,
}: {
  invoices: InvoiceWire[];
  page: PageMeta;
  /** The caller's campuses (from the session); shown when more than one. */
  campuses: CampusWire[];
  courses: FilterOption[];
  outstanding?: boolean;
  emptyState: { title: string; description: string; action?: ReactNode };
}) {
  const params = useListParams();
  const q = params.get("q") ?? "";
  const status = outstanding ? null : params.get("status");
  const campus = params.get("campus_id");
  const course = params.get("course_id");
  const overdue = params.get("overdue");
  const dueFrom = params.get("due_from");
  const dueTo = params.get("due_to");
  const active = [status, campus, course, overdue, dueFrom, dueTo].filter(
    Boolean,
  ).length;
  const filtered = Boolean(q) || active > 0;
  const clearAll = {
    q: null,
    status: null,
    campus_id: null,
    course_id: null,
    overdue: null,
    due_from: null,
    due_to: null,
  };

  const columns: DataTableColumn<InvoiceWire>[] = [
    {
      id: "number",
      header: "Fee invoice",
      isRowHeader: true,
      cell: (invoice) => (
        <RecordLink href={invoicePath(invoice.id)}>{invoice.number}</RecordLink>
      ),
    },
    {
      id: "student",
      header: "Student",
      cell: (invoice) => (
        <span className="flex flex-col">
          <span>{invoice.student.full_name}</span>
          <span className="text-caption text-text-secondary">
            {invoice.student.number}
          </span>
        </span>
      ),
    },
    {
      id: "course",
      header: "Course",
      visibleFrom: "desktop",
      cell: (invoice) => `${invoice.course.code} · ${invoice.campus.code}`,
    },
    {
      id: "due",
      header: "Due",
      visibleFrom: "tablet",
      cell: (invoice) => (
        <span className="flex flex-wrap items-center gap-2 whitespace-nowrap">
          {formatDate(invoice.due_date)}
          {invoice.overdue && <Badge tone="error">Overdue</Badge>}
        </span>
      ),
    },
    ...(outstanding
      ? []
      : [
          {
            id: "total",
            header: "Total",
            align: "end" as const,
            visibleFrom: "desktop" as const,
            cell: (invoice: InvoiceWire) => (
              <Amount minor={invoice.total_minor} />
            ),
          },
        ]),
    {
      id: "balance",
      header: "Balance",
      align: "end",
      cell: (invoice) => <Amount minor={invoice.balance_minor} strong />,
    },
    {
      id: "status",
      header: "Status",
      cell: (invoice) => (
        <Badge tone={INVOICE_STATUS_TONE[invoice.status]}>
          {INVOICE_STATUS_LABEL[invoice.status]}
        </Badge>
      ),
    },
  ];

  const filters = (
    <>
      {!outstanding && (
        <Select
          label="Status"
          options={[
            { id: ANY, label: "Any status" },
            ...(["ISSUED", "PARTIALLY_PAID", "PAID", "CANCELLED"] as const).map(
              (value) => ({ id: value, label: INVOICE_STATUS_LABEL[value] }),
            ),
          ]}
          value={status ?? ANY}
          onChange={(value) =>
            params.set({ status: value === ANY ? null : value })
          }
        />
      )}
      <Select
        label="Due"
        options={[
          { id: ANY, label: "Any due date" },
          { id: "true", label: "Overdue only" },
        ]}
        value={overdue ?? ANY}
        onChange={(value) =>
          params.set({ overdue: value === ANY ? null : value })
        }
      />
      {campuses.length > 1 && (
        <Select
          label="Campus"
          options={[
            { id: ANY, label: "All my campuses" },
            ...campusOptions(campuses),
          ]}
          value={campus ?? ANY}
          onChange={(value) =>
            params.set({ campus_id: value === ANY ? null : value })
          }
        />
      )}
      {courses.length > 0 && (
        <Select
          label="Course"
          options={[{ id: ANY, label: "Any course" }, ...courses]}
          value={course ?? ANY}
          onChange={(value) =>
            params.set({ course_id: value === ANY ? null : value })
          }
        />
      )}
      <DatePicker
        label="Due from"
        value={dueFrom}
        onChange={(iso) => params.set({ due_from: iso })}
      />
      <DatePicker
        label="Due to"
        value={dueTo}
        minValue={dueFrom ?? undefined}
        onChange={(iso) => params.set({ due_to: iso })}
      />
    </>
  );

  const noun = outstanding ? "unpaid fee invoice" : "fee invoice";
  return (
    <div className="flex min-w-0 flex-col gap-4">
      <FilterBar
        label={outstanding ? "Outstanding filters" : "Fee invoice filters"}
        search={
          <Search
            label="Search fee invoices"
            isLabelHidden
            placeholder="Invoice, admission or student number, or name"
            defaultValue={q}
            onSubmit={(value) => params.set({ q: value.trim() || null })}
            onClear={() => params.set({ q: null })}
          />
        }
        activeFilterCount={active}
        resultCount={`${page.total} ${page.total === 1 ? noun : `${noun}s`}`}
        onClear={() => params.set({ ...clearAll, q: q || null })}
        filters={filters}
      />
      <DataTable
        label={outstanding ? "Outstanding fee invoices" : "Fee invoices"}
        columns={columns}
        rows={invoices}
        getRowId={(invoice) => invoice.id}
        getRowLabel={(invoice) => invoice.number}
        mobileLayout="cards"
        emptyState={
          filtered
            ? {
                title: `No ${noun}s match these filters`,
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
            : emptyState
        }
        footer={
          page.total > page.limit ? (
            <Pagination
              label="Fee invoice pages"
              itemLabel="fee invoices"
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
