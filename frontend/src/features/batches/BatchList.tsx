"use client";

import {
  Badge,
  Button,
  DataTable,
  FilterBar,
  Pagination,
  Search,
  Select,
  type DataTableColumn,
  type SortDescriptor,
} from "@/design-system/components";
import { AddIcon } from "@/design-system/icons";
import type { BatchWire, RefWire } from "@/lib/api/batches";
import type { PageMeta } from "@/lib/api/server-read";
import { PermissionGate } from "@/lib/authz/PermissionGate";
import { useListParams } from "@/lib/navigation/list-params";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { formatDate } from "../shared/format";
import { RecordLink } from "../shared/RecordLink";

import {
  BATCH_MANAGE,
  BATCHES_PATH,
  batchPath,
  STATUS_LABEL,
  STATUS_TONE,
} from "./labels";
import { SeatMeter } from "./SeatMeter";

// ACA-05 Batches (Phase 02-6): the batches of the member's campuses with
// seat utilisation. Search, course, campus, status and seat filters and the
// sort live in the URL; the server renders the page. "New batch" only with
// batch.manage (UX only; the API refuses anyway).

const ANY = "any";
const SORTS: Record<string, string> = {
  start_date: "start_date",
  code: "code",
  name: "name",
};

export function NewBatchButton() {
  return (
    <PermissionGate permission={BATCH_MANAGE}>
      <Button href={`${BATCHES_PATH}/new`} iconStart={AddIcon}>
        New batch
      </Button>
    </PermissionGate>
  );
}

function sortDescriptor(sort: string | null): SortDescriptor {
  const value = sort ?? "-start_date";
  const columnId = value.replace(/^-/, "");
  return {
    columnId: columnId in SORTS ? columnId : "start_date",
    direction: value.startsWith("-") ? "descending" : "ascending",
  };
}

export function BatchList({
  batches,
  courses,
  page,
}: {
  batches: BatchWire[];
  courses: RefWire[];
  page: PageMeta;
}) {
  const params = useListParams();
  const { session, can } = useTenantSession();
  const q = params.get("q") ?? "";
  const status = params.get("status");
  const course = params.get("course_id");
  const campus = params.get("campus_id");
  const hasSeats = params.get("has_seats");
  const activeFilters = [status, course, campus, hasSeats].filter(
    Boolean,
  ).length;
  const filtered = Boolean(q) || activeFilters > 0;
  const showCampus = session.campusOptions.length > 1;

  const columns: DataTableColumn<BatchWire>[] = [
    {
      id: "code",
      header: "Code",
      isSortable: true,
      cell: (batch) => (
        <span className="font-medium text-text-primary">{batch.code}</span>
      ),
    },
    {
      id: "name",
      header: "Batch",
      isSortable: true,
      isRowHeader: true,
      cell: (batch) => (
        <span className="flex min-w-0 flex-col">
          <RecordLink href={batchPath(batch.id)}>{batch.name}</RecordLink>
          <span className="text-caption text-text-secondary">
            {[batch.course.code, batch.intake_label]
              .filter(Boolean)
              .join(" · ")}
          </span>
        </span>
      ),
    },
    ...(showCampus
      ? [
          {
            id: "campus",
            header: "Campus",
            visibleFrom: "tablet" as const,
            cell: (batch: BatchWire) => batch.campus.name,
          },
        ]
      : []),
    {
      id: "start_date",
      header: "Dates",
      isSortable: true,
      visibleFrom: "tablet",
      cell: (batch) =>
        `${formatDate(batch.start_date)} – ${formatDate(batch.end_date)}`,
    },
    {
      id: "seats",
      header: "Seats",
      cell: (batch) => (
        <SeatMeter
          capacity={batch.capacity}
          allocated={batch.allocated_count}
          compact
        />
      ),
    },
    {
      id: "available",
      header: "Available",
      visibleFrom: "desktop",
      cell: (batch) => (
        <span className="tabular-nums">{batch.available_seats}</span>
      ),
    },
    {
      id: "status",
      header: "Status",
      cell: (batch) => (
        <Badge tone={STATUS_TONE[batch.status]}>
          {STATUS_LABEL[batch.status]}
        </Badge>
      ),
    },
  ];

  const emptyState = filtered
    ? {
        title: "No batches match these filters",
        description: "Try another search term or clear the filters.",
        action: (
          <Button
            variant="secondary"
            onPress={() =>
              params.set({
                q: null,
                status: null,
                course_id: null,
                campus_id: null,
                has_seats: null,
              })
            }
          >
            Clear filters
          </Button>
        ),
      }
    : can(BATCH_MANAGE)
      ? {
          title: "No batches yet",
          description:
            "Create a batch for an active course so admitted students can be allocated and enrolled.",
          action: <NewBatchButton />,
        }
      : {
          title: "No batches yet",
          description:
            "Batches of your campuses appear here once they are created.",
        };

  return (
    <div className="flex min-w-0 flex-col gap-4">
      <FilterBar
        label="Batch filters"
        search={
          <Search
            label="Search batches"
            isLabelHidden
            placeholder="Search by code, name or intake"
            defaultValue={q}
            onSubmit={(value) => params.set({ q: value.trim() || null })}
            onClear={() => params.set({ q: null })}
          />
        }
        activeFilterCount={activeFilters}
        resultCount={`${page.total} ${page.total === 1 ? "batch" : "batches"}`}
        onClear={() =>
          params.set({
            status: null,
            course_id: null,
            campus_id: null,
            has_seats: null,
          })
        }
        filters={
          <>
            <Select
              label="Course"
              options={[
                { id: ANY, label: "Any course" },
                ...courses.map((c) => ({
                  id: c.id,
                  label: `${c.code} · ${c.name}`,
                })),
              ]}
              value={course ?? ANY}
              onChange={(value) =>
                params.set({ course_id: value === ANY ? null : value })
              }
            />
            {showCampus && (
              <Select
                label="Campus"
                options={[
                  { id: ANY, label: "Any campus" },
                  ...session.campusOptions.map((c) => ({
                    id: c.id,
                    label: c.name,
                  })),
                ]}
                value={campus ?? ANY}
                onChange={(value) =>
                  params.set({ campus_id: value === ANY ? null : value })
                }
              />
            )}
            <Select
              label="Status"
              options={[
                { id: ANY, label: "Any status" },
                { id: "OPEN", label: "Open" },
                { id: "CLOSED", label: "Closed" },
                { id: "CANCELLED", label: "Cancelled" },
              ]}
              value={status ?? ANY}
              onChange={(value) =>
                params.set({ status: value === ANY ? null : value })
              }
            />
            <Select
              label="Seats"
              options={[
                { id: ANY, label: "Any" },
                { id: "true", label: "Seats available" },
                { id: "false", label: "Full" },
              ]}
              value={hasSeats ?? ANY}
              onChange={(value) =>
                params.set({ has_seats: value === ANY ? null : value })
              }
            />
          </>
        }
      />
      <DataTable
        label="Batches"
        columns={columns}
        rows={batches}
        getRowId={(batch) => batch.id}
        getRowLabel={(batch) => batch.name}
        mobileLayout="cards"
        sort={sortDescriptor(params.get("sort"))}
        onSortChange={(sort) =>
          params.set({
            sort: sort
              ? `${sort.direction === "descending" ? "-" : ""}${sort.columnId}`
              : null,
          })
        }
        emptyState={emptyState}
        footer={
          page.total > page.limit ? (
            <Pagination
              label="Batch pages"
              itemLabel="batches"
              page={Math.floor(page.offset / page.limit) + 1}
              pageSize={page.limit}
              totalItems={page.total}
              onPageChange={(next) =>
                params.set(
                  { offset: next > 1 ? String((next - 1) * page.limit) : null },
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
