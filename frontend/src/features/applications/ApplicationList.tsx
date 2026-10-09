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
import type { ApplicationListItemWire } from "@/lib/api/admissions";
import type { PageMeta } from "@/lib/api/server-read";
import { PermissionGate } from "@/lib/authz/PermissionGate";
import { useListParams } from "@/lib/navigation/list-params";
import { useTenantSession } from "@/lib/session/SessionProvider";

import { formatDate } from "../shared/format";
import { RecordLink } from "../shared/RecordLink";

import {
  APPLICATION_CREATE,
  APPLICATIONS_PATH,
  applicationPath,
  STATUS_FILTERS,
  STATUS_LABEL,
  STATUS_TONE,
} from "./labels";

// ADM-05 Applications (Phase 02-2; ADR-0021 §14): applications of the
// member's campuses, newest first. Search (name or application number),
// status and "Mine" live in the URL; the server renders the page. Contact
// details are never searched from here (no personal data in URLs beyond the
// search box term).

const ANY = "any";
const SORTABLE: Record<string, string> = {
  number: "number",
  full_name: "full_name",
  created_at: "created_at",
};

export function NewApplicationButton() {
  return (
    <PermissionGate permission={APPLICATION_CREATE}>
      <Button href={`${APPLICATIONS_PATH}/new`} iconStart={AddIcon}>
        New application
      </Button>
    </PermissionGate>
  );
}

function sortDescriptor(sort: string | null): SortDescriptor {
  const value = sort ?? "-created_at";
  const columnId = value.replace(/^-/, "");
  return {
    columnId: columnId in SORTABLE ? columnId : "created_at",
    direction: value.startsWith("-") ? "descending" : "ascending",
  };
}

export function ApplicationList({
  applications,
  page,
}: {
  applications: ApplicationListItemWire[];
  page: PageMeta;
}) {
  const params = useListParams();
  const { can } = useTenantSession();
  const q = params.get("q") ?? "";
  const status = params.get("status");
  const mine = params.get("owner") === "me";
  const filtered = Boolean(q || status || mine);

  const columns: DataTableColumn<ApplicationListItemWire>[] = [
    {
      id: "number",
      header: "Application",
      isSortable: true,
      cell: (item) => (
        <span className="font-medium text-text-primary">{item.number}</span>
      ),
    },
    {
      id: "full_name",
      header: "Applicant",
      isSortable: true,
      isRowHeader: true,
      cell: (item) => (
        <RecordLink href={applicationPath(item.id)}>
          {item.full_name}
        </RecordLink>
      ),
    },
    {
      id: "course",
      header: "Course",
      cell: (item) => item.course_code,
    },
    {
      id: "campus",
      header: "Campus",
      visibleFrom: "tablet",
      cell: (item) => item.campus_code,
    },
    {
      id: "status",
      header: "Status",
      cell: (item) => (
        <Badge tone={STATUS_TONE[item.status]}>
          {STATUS_LABEL[item.status]}
        </Badge>
      ),
    },
    {
      id: "documents",
      header: "Documents pending",
      visibleFrom: "tablet",
      cell: (item) =>
        item.documents_pending > 0 ? String(item.documents_pending) : "None",
    },
    {
      id: "created_at",
      header: "Started",
      isSortable: true,
      visibleFrom: "desktop",
      cell: (item) => formatDate(item.created_at),
    },
  ];

  const emptyState = filtered
    ? {
        title: "No applications match these filters",
        description: "Try another search term or clear the filters.",
        action: (
          <Button
            variant="secondary"
            onPress={() => params.set({ q: null, status: null, owner: null })}
          >
            Clear filters
          </Button>
        ),
      }
    : can(APPLICATION_CREATE)
      ? {
          title: "No applications yet",
          description:
            "Start an application from a lead that is ready to apply, or for a walk-in applicant.",
          action: <NewApplicationButton />,
        }
      : {
          title: "No applications yet",
          description: "Applications of your campuses appear here.",
        };

  return (
    <div className="flex min-w-0 flex-col gap-4">
      <FilterBar
        label="Application filters"
        search={
          <Search
            label="Search applications"
            isLabelHidden
            placeholder="Search by name or application number"
            defaultValue={q}
            onSubmit={(value) => params.set({ q: value.trim() || null })}
            onClear={() => params.set({ q: null })}
          />
        }
        activeFilterCount={[status, mine].filter(Boolean).length}
        resultCount={`${page.total} ${page.total === 1 ? "application" : "applications"}`}
        onClear={() => params.set({ status: null, owner: null })}
        filters={
          <>
            <Select
              label="Status"
              options={[
                { id: ANY, label: "Any status" },
                ...STATUS_FILTERS.map((value) => ({
                  id: value,
                  label: STATUS_LABEL[value],
                })),
              ]}
              value={status ?? ANY}
              onChange={(value) =>
                params.set({ status: value === ANY ? null : value })
              }
            />
            <Select
              label="Owner"
              options={[
                { id: ANY, label: "Anyone" },
                { id: "me", label: "My applications" },
              ]}
              value={mine ? "me" : ANY}
              onChange={(value) =>
                params.set({ owner: value === "me" ? "me" : null })
              }
            />
          </>
        }
      />
      <DataTable
        label="Applications"
        columns={columns}
        rows={applications}
        getRowId={(item) => item.id}
        getRowLabel={(item) => `${item.number} ${item.full_name}`}
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
              label="Application pages"
              itemLabel="applications"
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
