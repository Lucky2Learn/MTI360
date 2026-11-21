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
import type { TenantWire } from "@/lib/api/platform-tenants";
import type { PageMeta } from "@/lib/api/server-read";
import { useListParams } from "@/lib/navigation/list-params";
import { usePlatformSession } from "@/lib/session/PlatformSessionProvider";

import { formatDate } from "../shared/format";
import { RecordLink } from "../shared/RecordLink";

import {
  NEW_TENANT_PATH,
  STATUS_LABEL,
  STATUS_TONE,
  TENANT_CREATE,
  TENANT_STATUSES,
  tenantPath,
} from "./labels";
import { tenantSort } from "./query";

// PLAT-04 Tenant list (Platform Administration). Every institute for a
// platform session with tenant.read: search by name, filter by lifecycle
// status, sort and pages live in the URL; the server renders the page.
// "New tenant" is offered only with tenant.create (UX only; the platform API
// refuses the request anyway).

const ANY = "any";

export function NewTenantButton() {
  const { can } = usePlatformSession();
  if (!can(TENANT_CREATE)) return null;
  return (
    <Button href={NEW_TENANT_PATH} iconStart={AddIcon}>
      New tenant
    </Button>
  );
}

function sortDescriptor(sort: string | null): SortDescriptor {
  const value = tenantSort(sort);
  return {
    columnId: value.replace(/^-/, ""),
    direction: value.startsWith("-") ? "descending" : "ascending",
  };
}

export function TenantList({
  tenants,
  page,
}: {
  tenants: TenantWire[];
  page: PageMeta;
}) {
  const params = useListParams();
  const { can } = usePlatformSession();
  const q = params.get("q") ?? "";
  const status = params.get("status");
  const filtered = Boolean(q || status);

  const columns: DataTableColumn<TenantWire>[] = [
    {
      id: "name",
      header: "Institute",
      isSortable: true,
      isRowHeader: true,
      cell: (tenant) => (
        <RecordLink href={tenantPath(tenant.id)}>{tenant.name}</RecordLink>
      ),
    },
    {
      id: "status",
      header: "Status",
      cell: (tenant) => (
        <Badge tone={STATUS_TONE[tenant.status]}>
          {STATUS_LABEL[tenant.status]}
        </Badge>
      ),
    },
    {
      id: "created_at",
      header: "Created",
      isSortable: true,
      cell: (tenant) => formatDate(tenant.created_at),
    },
    {
      id: "updated_at",
      header: "Last updated",
      visibleFrom: "tablet",
      cell: (tenant) => formatDate(tenant.updated_at),
    },
  ];

  // A page past the end (a stale link after tenants changed) is not "empty".
  const emptyState =
    page.total > 0
      ? {
          title: "No tenants on this page",
          description: "The list has fewer pages than this link expects.",
          action: (
            <Button variant="secondary" onPress={() => params.set({})}>
              Go to the first page
            </Button>
          ),
        }
      : filtered
        ? {
            title: "No tenants match these filters",
            description: "Try another search term or clear the filters.",
            action: (
              <Button
                variant="secondary"
                onPress={() => params.set({ q: null, status: null })}
              >
                Clear filters
              </Button>
            ),
          }
        : can(TENANT_CREATE)
          ? {
              title: "No tenants yet",
              description:
                "Provision the first institute. Its administrator receives an invitation to join.",
              action: <NewTenantButton />,
            }
          : {
              title: "No tenants yet",
              description: "Institutes appear here once they are provisioned.",
            };

  return (
    <div className="flex min-w-0 flex-col gap-4">
      <FilterBar
        label="Tenant filters"
        search={
          <Search
            label="Search tenants"
            isLabelHidden
            placeholder="Search by institute name"
            defaultValue={q}
            onSubmit={(value) => params.set({ q: value.trim() || null })}
            onClear={() => params.set({ q: null })}
          />
        }
        activeFilterCount={status ? 1 : 0}
        resultCount={`${page.total} ${page.total === 1 ? "tenant" : "tenants"}`}
        onClear={() => params.set({ status: null })}
        filters={
          // One cell of the FilterBar's filter grid (the shared layout).
          <Select
            label="Status"
            options={[
              { id: ANY, label: "Any status" },
              ...TENANT_STATUSES.map((id) => ({
                id,
                label: STATUS_LABEL[id],
              })),
            ]}
            value={status ?? ANY}
            onChange={(value) =>
              params.set({ status: value === ANY ? null : value })
            }
          />
        }
      />
      <DataTable
        label="Tenants"
        columns={columns}
        rows={tenants}
        getRowId={(tenant) => tenant.id}
        getRowLabel={(tenant) => tenant.name}
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
              label="Tenant pages"
              itemLabel="tenants"
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
